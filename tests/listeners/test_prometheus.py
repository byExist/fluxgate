"""Tests for PrometheusListener."""

import pytest

from fluxgate.signal import Signal
from typing import get_args

from fluxgate.state import State

pytest.importorskip("prometheus_client")

from prometheus_client import Gauge, Counter, REGISTRY
from fluxgate.listeners.prometheus import (
    PrometheusListener,
    _STATE_GAUGE,  # type: ignore
    _STATE_TRANSITION,  # type: ignore
)


def _get_gauge_value(gauge: Gauge, **labels: str) -> float | None:
    """Helper to get gauge value via REGISTRY."""
    for metric in REGISTRY.collect():
        if metric.name == gauge._name:  # type: ignore
            for sample in metric.samples:
                if sample.labels == labels:
                    return sample.value
    return None


def _get_counter_value(counter: Counter, **labels: str) -> float | None:
    """Helper to get counter value via REGISTRY."""
    for metric in REGISTRY.collect():
        if metric.name == counter._name:  # type: ignore
            for sample in metric.samples:
                if sample.name.endswith("_total") and sample.labels == labels:
                    return sample.value
    return None


def test_prometheus_listener_basic():
    """PrometheusListener updates Prometheus metrics."""
    listener = PrometheusListener(name="test_circuit")

    signal = Signal(
        old_state="closed",
        new_state="open",
        timestamp=1234567890.0,
    )

    listener(signal)

    open_value = _get_gauge_value(
        _STATE_GAUGE, circuit_name="test_circuit", state="open"
    )
    closed_value = _get_gauge_value(
        _STATE_GAUGE, circuit_name="test_circuit", state="closed"
    )

    assert open_value == 1.0
    assert closed_value == 0.0


def test_prometheus_listener_state_transitions():
    """PrometheusListener tracks state transitions."""
    listener = PrometheusListener(name="transition_test")

    signal = Signal(
        old_state="closed",
        new_state="open",
        timestamp=1234567890.0,
    )

    initial_count = _get_counter_value(
        _STATE_TRANSITION,
        circuit_name="transition_test",
        old_state="closed",
        new_state="open",
    )
    initial_count = initial_count or 0.0

    listener(signal)

    final_count = _get_counter_value(
        _STATE_TRANSITION,
        circuit_name="transition_test",
        old_state="closed",
        new_state="open",
    )

    assert final_count == initial_count + 1


def test_prometheus_listener_multiple_circuits():
    """PrometheusListener handles multiple circuits independently."""
    listener_a = PrometheusListener(name="circuit_a")
    listener_b = PrometheusListener(name="circuit_b")

    signal1 = Signal(
        old_state="closed",
        new_state="open",
        timestamp=1.0,
    )
    signal2 = Signal(
        old_state="closed",
        new_state="half_open",
        timestamp=2.0,
    )

    listener_a(signal1)
    listener_b(signal2)

    circuit_a_open = _get_gauge_value(
        _STATE_GAUGE, circuit_name="circuit_a", state="open"
    )
    circuit_b_half_open = _get_gauge_value(
        _STATE_GAUGE, circuit_name="circuit_b", state="half_open"
    )

    assert circuit_a_open == 1.0
    assert circuit_b_half_open == 1.0


def test_prometheus_listener_all_states():
    """PrometheusListener correctly sets gauges for all states."""
    listener = PrometheusListener(name="all_states_test")

    signal = Signal(
        old_state="closed",
        new_state="open",
        timestamp=1.0,
    )

    listener(signal)

    for state in get_args(State):
        value = _get_gauge_value(
            _STATE_GAUGE, circuit_name="all_states_test", state=state
        )
        expected_value = 1.0 if state == "open" else 0.0
        assert value == expected_value


async def test_prometheus_listener_with_async_circuit_breaker():
    """PrometheusListener works with AsyncCircuitBreaker."""
    from fluxgate import AsyncCircuitBreaker

    listener = PrometheusListener(name="async_prom_test")
    cb = AsyncCircuitBreaker(listeners=[listener])

    await cb.reset()

    closed_value = _get_gauge_value(
        _STATE_GAUGE, circuit_name="async_prom_test", state="closed"
    )
    assert closed_value == 1.0


def test_prometheus_listener_close_removes_timeseries():
    """``close()`` drops every timeseries this listener registered."""
    from prometheus_client import CollectorRegistry

    custom_registry = CollectorRegistry()
    listener = PrometheusListener(name="ephemeral", registry=custom_registry)

    signal = Signal(
        old_state="closed",
        new_state="open",
        timestamp=1.0,
    )
    listener(signal)

    has_before = any(
        sample.labels.get("circuit_name") == "ephemeral"
        for metric in custom_registry.collect()
        for sample in metric.samples
    )
    assert has_before, "expected the timeseries to be present before close()"

    listener.close()

    still_has = any(
        sample.labels.get("circuit_name") == "ephemeral"
        for metric in custom_registry.collect()
        for sample in metric.samples
    )
    assert not still_has, (
        "close() must drop every timeseries labelled with the circuit name"
    )


def test_prometheus_listener_close_is_idempotent():
    """``close()`` no-ops on a listener whose labelset was never emitted."""
    from prometheus_client import CollectorRegistry

    custom_registry = CollectorRegistry()
    listener = PrometheusListener(name="never_emitted", registry=custom_registry)

    # No signal sent — no labels created. close() must not raise.
    listener.close()
    listener.close()


def test_prometheus_listener_custom_registry_isolation():
    """``registry=`` kwarg isolates metrics from the default ``REGISTRY``."""
    from prometheus_client import CollectorRegistry

    custom_registry = CollectorRegistry()
    listener = PrometheusListener(name="isolated_test", registry=custom_registry)

    signal = Signal(
        old_state="closed",
        new_state="open",
        timestamp=1.0,
    )
    listener(signal)

    open_in_custom: float | None = None
    for metric in custom_registry.collect():
        if metric.name == "circuit_breaker_state":
            for sample in metric.samples:
                if (
                    sample.labels.get("circuit_name") == "isolated_test"
                    and sample.labels.get("state") == "open"
                ):
                    open_in_custom = sample.value
    assert open_in_custom == 1.0, "expected metric in the custom registry"

    open_in_default = _get_gauge_value(
        _STATE_GAUGE, circuit_name="isolated_test", state="open"
    )
    assert open_in_default is None, (
        "isolated_test must not appear on the default REGISTRY"
    )
