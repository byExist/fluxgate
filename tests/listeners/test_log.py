"""Tests for LogListener."""

import logging

from pytest import LogCaptureFixture

from fluxgate.listeners.log import LogListener
from fluxgate.signal import Signal
from fluxgate.state import State


def test_logging_listener_basic(caplog: LogCaptureFixture):
    """LogListener produces correct log messages."""
    listener = LogListener(name="payment_api")

    signal = Signal(
        old_state="closed",
        new_state="open",
        timestamp=1234567890.0,
    )

    with caplog.at_level(logging.INFO):
        listener(signal)

    assert len(caplog.records) == 1
    assert "payment_api" in caplog.text
    assert "closed" in caplog.text
    assert "open" in caplog.text


def test_logging_listener_multiple_transitions(caplog: LogCaptureFixture):
    """LogListener handles multiple transitions."""
    listener = LogListener(name="multi")

    transitions: list[tuple[State, State]] = [
        ("closed", "open"),
        ("open", "half_open"),
        ("half_open", "closed"),
    ]

    with caplog.at_level(logging.INFO):
        for old_state, new_state in transitions:
            signal = Signal(
                old_state=old_state,
                new_state=new_state,
                timestamp=1234567890.0,
            )
            listener(signal)

    assert len(caplog.records) == 3


def test_logging_listener_all_states(caplog: LogCaptureFixture):
    """LogListener logs all state transitions correctly."""
    listener = LogListener(name="comprehensive_test")

    all_transitions: list[tuple[State, State]] = [
        ("closed", "open"),
        ("open", "half_open"),
        ("half_open", "closed"),
        ("closed", "disabled"),
        ("disabled", "closed"),
        ("closed", "metrics_only"),
        ("metrics_only", "closed"),
        ("closed", "forced_open"),
        ("forced_open", "closed"),
    ]

    with caplog.at_level(logging.INFO):
        for old_state, new_state in all_transitions:
            signal = Signal(
                old_state=old_state,
                new_state=new_state,
                timestamp=1234567890.0,
            )
            listener(signal)

    assert len(caplog.records) == len(all_transitions)
    assert "comprehensive_test" in caplog.text


def test_logging_listener_timestamp_formatting(caplog: LogCaptureFixture):
    """LogListener formats timestamps correctly."""
    listener = LogListener(name="ts_test")

    signal = Signal(
        old_state="closed",
        new_state="open",
        timestamp=1234567890.0,
    )

    with caplog.at_level(logging.INFO):
        listener(signal)

    assert len(caplog.records) == 1
    log_message = caplog.text
    assert "[" in log_message
    assert "]" in log_message


async def test_logging_listener_with_async_circuit_breaker(caplog: LogCaptureFixture):
    """LogListener works with AsyncCircuitBreaker."""
    from fluxgate import AsyncCircuitBreaker

    listener = LogListener(name="async_test")
    cb = AsyncCircuitBreaker(listeners=[listener])

    with caplog.at_level(logging.INFO):
        await cb.reset()

    assert len(caplog.records) >= 1
    assert "async_test" in caplog.text


def test_logging_listener_default_logger_is_fluxgate_namespaced(
    caplog: LogCaptureFixture,
):
    """LogListener emits on a fluxgate-prefixed logger by default, not root."""
    listener = LogListener(name="ns_default")

    signal = Signal(
        old_state="closed",
        new_state="open",
        timestamp=1234567890.0,
    )

    with caplog.at_level(logging.INFO):
        listener(signal)

    assert len(caplog.records) == 1
    assert caplog.records[0].name.startswith("fluxgate"), (
        f"expected fluxgate-prefixed logger, got {caplog.records[0].name!r}"
    )


def test_logging_listener_custom_logger(caplog: LogCaptureFixture):
    """LogListener uses custom logger when provided."""
    custom_logger = logging.getLogger("custom.circuit_breaker")
    listener = LogListener(name="custom_test", logger=custom_logger)

    signal = Signal(
        old_state="closed",
        new_state="open",
        timestamp=1234567890.0,
    )

    with caplog.at_level(logging.INFO, logger="custom.circuit_breaker"):
        listener(signal)

    assert len(caplog.records) == 1
    assert caplog.records[0].name == "custom.circuit_breaker"
    assert "custom_test" in caplog.text


def test_logging_listener_default_level_map(caplog: LogCaptureFixture):
    """LogListener uses WARNING for OPEN state by default."""
    listener = LogListener(name="level_default")

    signal_open = Signal(
        old_state="closed",
        new_state="open",
        timestamp=1234567890.0,
    )

    signal_closed = Signal(
        old_state="open",
        new_state="closed",
        timestamp=1234567890.0,
    )

    with caplog.at_level(logging.DEBUG):
        listener(signal_open)
        listener(signal_closed)

    assert len(caplog.records) == 2
    assert caplog.records[0].levelno == logging.WARNING
    assert caplog.records[1].levelno == logging.INFO


def test_logging_listener_custom_level_map(caplog: LogCaptureFixture):
    """LogListener uses custom level_map when provided."""
    level_map: dict[State, int] = {
        "open": logging.ERROR,
        "closed": logging.DEBUG,
    }
    listener = LogListener(name="level_custom", level_map=level_map)

    signal_open = Signal(
        old_state="closed",
        new_state="open",
        timestamp=1234567890.0,
    )

    signal_closed = Signal(
        old_state="open",
        new_state="closed",
        timestamp=1234567890.0,
    )

    with caplog.at_level(logging.DEBUG):
        listener(signal_open)
        listener(signal_closed)

    assert len(caplog.records) == 2
    assert caplog.records[0].levelno == logging.ERROR
    assert caplog.records[1].levelno == logging.DEBUG


def test_logging_listener_partial_level_map(caplog: LogCaptureFixture):
    """LogListener merges partial level_map with defaults."""
    level_map: dict[State, int] = {"open": logging.CRITICAL}
    listener = LogListener(name="level_partial", level_map=level_map)

    signal_open = Signal(
        old_state="closed",
        new_state="open",
        timestamp=1234567890.0,
    )

    signal_half_open = Signal(
        old_state="open",
        new_state="half_open",
        timestamp=1234567890.0,
    )

    with caplog.at_level(logging.DEBUG):
        listener(signal_open)
        listener(signal_half_open)

    assert len(caplog.records) == 2
    assert caplog.records[0].levelno == logging.CRITICAL  # overridden
    assert caplog.records[1].levelno == logging.INFO  # default
