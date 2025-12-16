"""Tests for PrometheusListener."""

import pytest

from fluxgate.signal import Signal
from fluxgate.state import StateEnum

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
    listener = PrometheusListener()

    signal = Signal(
        circuit_name="test_circuit",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
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
    listener = PrometheusListener()

    signal = Signal(
        circuit_name="transition_test",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
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
    listener = PrometheusListener()

    signal1 = Signal(
        circuit_name="circuit_a",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
        timestamp=1.0,
    )
    signal2 = Signal(
        circuit_name="circuit_b",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.HALF_OPEN,
        timestamp=2.0,
    )

    listener(signal1)
    listener(signal2)

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
    listener = PrometheusListener()

    signal = Signal(
        circuit_name="all_states_test",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
        timestamp=1.0,
    )

    listener(signal)

    for state in StateEnum:
        value = _get_gauge_value(
            _STATE_GAUGE, circuit_name="all_states_test", state=state.value
        )
        expected_value = 1.0 if state == StateEnum.OPEN else 0.0
        assert value == expected_value


async def test_prometheus_listener_with_async_circuit_breaker():
    """PrometheusListener works with AsyncCircuitBreaker."""
    from fluxgate import AsyncCircuitBreaker

    listener = PrometheusListener()
    cb = AsyncCircuitBreaker(name="async_prom_test", listeners=[listener])

    await cb.reset()

    closed_value = _get_gauge_value(
        _STATE_GAUGE, circuit_name="async_prom_test", state="closed"
    )
    assert closed_value == 1.0
