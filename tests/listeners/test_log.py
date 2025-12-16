"""Tests for LogListener."""

import logging

from pytest import LogCaptureFixture

from fluxgate.listeners.log import LogListener
from fluxgate.signal import Signal
from fluxgate.state import StateEnum


def test_logging_listener_basic(caplog: LogCaptureFixture):
    """LogListener produces correct log messages."""
    listener = LogListener()

    signal = Signal(
        circuit_name="payment_api",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
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
    listener = LogListener()

    transitions = [
        (StateEnum.CLOSED, StateEnum.OPEN),
        (StateEnum.OPEN, StateEnum.HALF_OPEN),
        (StateEnum.HALF_OPEN, StateEnum.CLOSED),
    ]

    with caplog.at_level(logging.INFO):
        for old_state, new_state in transitions:
            signal = Signal(
                circuit_name="test_circuit",
                old_state=old_state,
                new_state=new_state,
                timestamp=1234567890.0,
            )
            listener(signal)

    assert len(caplog.records) == 3


def test_logging_listener_all_states(caplog: LogCaptureFixture):
    """LogListener logs all state transitions correctly."""
    listener = LogListener()

    all_transitions = [
        (StateEnum.CLOSED, StateEnum.OPEN),
        (StateEnum.OPEN, StateEnum.HALF_OPEN),
        (StateEnum.HALF_OPEN, StateEnum.CLOSED),
        (StateEnum.CLOSED, StateEnum.DISABLED),
        (StateEnum.DISABLED, StateEnum.CLOSED),
        (StateEnum.CLOSED, StateEnum.METRICS_ONLY),
        (StateEnum.METRICS_ONLY, StateEnum.CLOSED),
        (StateEnum.CLOSED, StateEnum.FORCED_OPEN),
        (StateEnum.FORCED_OPEN, StateEnum.CLOSED),
    ]

    with caplog.at_level(logging.INFO):
        for old_state, new_state in all_transitions:
            signal = Signal(
                circuit_name="comprehensive_test",
                old_state=old_state,
                new_state=new_state,
                timestamp=1234567890.0,
            )
            listener(signal)

    assert len(caplog.records) == len(all_transitions)
    assert "comprehensive_test" in caplog.text


def test_logging_listener_timestamp_formatting(caplog: LogCaptureFixture):
    """LogListener formats timestamps correctly."""
    listener = LogListener()

    signal = Signal(
        circuit_name="test",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
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

    listener = LogListener()
    cb = AsyncCircuitBreaker(name="async_test", listeners=[listener])

    with caplog.at_level(logging.INFO):
        await cb.reset()

    assert len(caplog.records) >= 1
    assert "async_test" in caplog.text


def test_logging_listener_custom_logger(caplog: LogCaptureFixture):
    """LogListener uses custom logger when provided."""
    custom_logger = logging.getLogger("custom.circuit_breaker")
    listener = LogListener(logger=custom_logger)

    signal = Signal(
        circuit_name="custom_test",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
        timestamp=1234567890.0,
    )

    with caplog.at_level(logging.INFO, logger="custom.circuit_breaker"):
        listener(signal)

    assert len(caplog.records) == 1
    assert caplog.records[0].name == "custom.circuit_breaker"
    assert "custom_test" in caplog.text


def test_logging_listener_default_level_map(caplog: LogCaptureFixture):
    """LogListener uses WARNING for OPEN state by default."""
    listener = LogListener()

    signal_open = Signal(
        circuit_name="test",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
        timestamp=1234567890.0,
    )

    signal_closed = Signal(
        circuit_name="test",
        old_state=StateEnum.OPEN,
        new_state=StateEnum.CLOSED,
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
    level_map = {
        StateEnum.OPEN: logging.ERROR,
        StateEnum.CLOSED: logging.DEBUG,
    }
    listener = LogListener(level_map=level_map)

    signal_open = Signal(
        circuit_name="test",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
        timestamp=1234567890.0,
    )

    signal_closed = Signal(
        circuit_name="test",
        old_state=StateEnum.OPEN,
        new_state=StateEnum.CLOSED,
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
    level_map = {StateEnum.OPEN: logging.CRITICAL}
    listener = LogListener(level_map=level_map)

    signal_open = Signal(
        circuit_name="test",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
        timestamp=1234567890.0,
    )

    signal_half_open = Signal(
        circuit_name="test",
        old_state=StateEnum.OPEN,
        new_state=StateEnum.HALF_OPEN,
        timestamp=1234567890.0,
    )

    with caplog.at_level(logging.DEBUG):
        listener(signal_open)
        listener(signal_half_open)

    assert len(caplog.records) == 2
    assert caplog.records[0].levelno == logging.CRITICAL  # overridden
    assert caplog.records[1].levelno == logging.INFO  # default
