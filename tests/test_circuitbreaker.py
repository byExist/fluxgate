"""Tests for CircuitBreaker (sync and async)."""

import asyncio

import pytest
from freezegun.api import FrozenDateTimeFactory

from fluxgate import (
    AsyncCircuitBreaker,
    CallNotPermittedError,
    CircuitBreaker,
    StateEnum,
)
from fluxgate.permits import All, Random
from fluxgate.retries import Cooldown
from fluxgate.signal import Signal
from fluxgate.trackers import TypeOf
from fluxgate.trippers import FailureRate, FailureStreak, MinRequests


def success_func(x: int = 1) -> int:
    return x * 2


def failing_func() -> None:
    raise ValueError("fail")


async def async_success_func(x: int = 1) -> int:
    return x * 2


async def async_failing_func() -> None:
    raise ValueError("fail")


def test_call_passes_through():
    """Successful calls pass through when circuit is CLOSED."""
    cb = CircuitBreaker(name="test")

    assert cb.call(success_func, 5) == 10
    assert cb.call(success_func, 10) == 20

    info = cb.info()
    assert info.state == StateEnum.CLOSED.value
    assert info.metrics.total_count == 2
    assert info.metrics.failure_count == 0


def test_decorator_usage():
    """CircuitBreaker works as a decorator."""
    cb = CircuitBreaker(name="test")

    @cb
    def decorated(x: int) -> int:
        return x + 1

    assert decorated(5) == 6
    assert decorated(10) == 11
    assert cb.info().metrics.total_count == 2


def test_failure_is_recorded():
    """Failures are recorded in metrics."""
    cb = CircuitBreaker(
        name="test",
        tripper=MinRequests(10) & FailureRate(0.5),
    )

    with pytest.raises(ValueError):
        cb.call(failing_func)

    info = cb.info()
    assert info.metrics.total_count == 1
    assert info.metrics.failure_count == 1


def test_closed_to_open_on_failure_threshold():
    """Circuit opens when failure rate exceeds threshold."""
    cb = CircuitBreaker(
        name="test",
        tripper=MinRequests(3) & FailureRate(0.5),
    )

    for _ in range(3):
        with pytest.raises(ValueError):
            cb.call(failing_func)

    assert cb.info().state == StateEnum.OPEN.value


def test_open_state_blocks_calls():
    """Circuit blocks calls with CallNotPermittedError when OPEN."""
    cb = CircuitBreaker(
        name="test",
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(10.0),
    )

    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(failing_func)

    with pytest.raises(CallNotPermittedError):
        cb.call(success_func)


def test_open_to_half_open_after_cooldown(freezer: FrozenDateTimeFactory):
    """Circuit transitions to HALF_OPEN after cooldown period."""
    cb = CircuitBreaker(
        name="test",
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(60.0),
        permit=All(),
    )

    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(failing_func)

    assert cb.info().state == StateEnum.OPEN.value

    freezer.tick(61)
    result = cb.call(success_func)

    assert result == 2
    assert cb.info().state in [StateEnum.HALF_OPEN.value, StateEnum.CLOSED.value]


def test_half_open_to_closed_on_success(freezer: FrozenDateTimeFactory):
    """Circuit closes after successful calls in HALF_OPEN state."""
    cb = CircuitBreaker(
        name="test",
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(60.0),
        permit=All(),
    )

    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(failing_func)

    freezer.tick(61)
    for _ in range(3):
        cb.call(success_func)

    assert cb.info().state == StateEnum.CLOSED.value


def test_half_open_to_open_on_failure(freezer: FrozenDateTimeFactory):
    """Circuit reopens if failures continue in HALF_OPEN state."""
    cb = CircuitBreaker(
        name="test",
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(60.0),
        permit=All(),
    )

    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(failing_func)

    initial_reopens = cb.info().reopens

    freezer.tick(61)
    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(failing_func)

    assert cb.info().state == StateEnum.OPEN.value
    assert cb.info().reopens == initial_reopens + 1


def test_half_open_permit_blocks_calls(freezer: FrozenDateTimeFactory):
    """Calls blocked by permit in HALF_OPEN state raise CallNotPermittedError."""
    cb = CircuitBreaker(
        name="test",
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(60.0),
        permit=Random(0.0),
    )

    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(failing_func)

    freezer.tick(61)
    with pytest.raises(CallNotPermittedError):
        cb.call(success_func)


def test_reset_transitions_to_closed():
    """reset() transitions circuit to CLOSED state."""
    cb = CircuitBreaker(
        name="test",
        tripper=MinRequests(2) & FailureRate(0.5),
    )

    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(failing_func)

    assert cb.info().state == StateEnum.OPEN.value

    cb.reset()
    assert cb.info().state == StateEnum.CLOSED.value


def test_disable_allows_all_calls():
    """disable() allows all calls without state changes."""
    cb = CircuitBreaker(name="test")
    cb.disable()

    assert cb.info().state == StateEnum.DISABLED.value

    with pytest.raises(ValueError):
        cb.call(failing_func)

    assert cb.info().state == StateEnum.DISABLED.value


def test_force_open_blocks_all_calls():
    """force_open() blocks all calls."""
    cb = CircuitBreaker(name="test")
    cb.force_open()

    assert cb.info().state == StateEnum.FORCED_OPEN.value

    with pytest.raises(CallNotPermittedError):
        cb.call(success_func)


def test_metrics_only_collects_without_tripping():
    """metrics_only() enables metric collection without circuit breaking."""
    cb = CircuitBreaker(
        name="test",
        tripper=MinRequests(2) & FailureRate(0.5),
    )
    cb.metrics_only()

    for _ in range(5):
        with pytest.raises(ValueError):
            cb.call(failing_func)

    info = cb.info()
    assert info.state == StateEnum.METRICS_ONLY.value
    assert info.metrics.failure_count == 5


def test_untracked_exceptions_propagate():
    """Exceptions not tracked by tracker are propagated without recording."""
    cb = CircuitBreaker(name="test", tracker=TypeOf(ValueError))

    def raises_type_error() -> None:
        raise TypeError("not tracked")

    with pytest.raises(TypeError, match="not tracked"):
        cb.call(raises_type_error)

    info = cb.info()
    assert info.metrics.total_count == 0
    assert info.metrics.failure_count == 0


def test_half_open_untracked_exception_propagates(freezer: FrozenDateTimeFactory):
    """Untracked exceptions in HALF_OPEN propagate without state change."""
    cb = CircuitBreaker(
        name="test",
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(60.0),
        permit=All(),
    )

    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(failing_func)

    def raises_type_error() -> None:
        raise TypeError("not tracked")

    freezer.tick(61)
    with pytest.raises(TypeError):
        cb.call(raises_type_error)

    assert cb.info().state == StateEnum.HALF_OPEN.value


def test_all_exception_types_tracked_by_default():
    """Default tracker (All) tracks all exception types."""
    cb = CircuitBreaker(
        name="test",
        tripper=MinRequests(3) & FailureRate(0.5),
    )

    def raise_value_error() -> None:
        raise ValueError("a")

    def raise_type_error() -> None:
        raise TypeError("b")

    def raise_runtime_error() -> None:
        raise RuntimeError("c")

    for func in [raise_value_error, raise_type_error, raise_runtime_error]:
        with pytest.raises(Exception):
            cb.call(func)

    assert cb.info().state == StateEnum.OPEN.value


def test_listener_notification_on_state_change():
    """Listeners are notified on state transitions."""
    signals: list[Signal] = []

    def listener(signal: Signal) -> None:
        signals.append(signal)

    cb = CircuitBreaker(
        name="test",
        tripper=MinRequests(2) & FailureRate(0.5),
        listeners=[listener],
    )

    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(failing_func)

    assert len(signals) == 1
    assert signals[0].old_state == StateEnum.CLOSED
    assert signals[0].new_state == StateEnum.OPEN

    cb.reset()
    assert len(signals) == 2


def test_listener_exception_does_not_break_operation():
    """Failing listeners don't break circuit breaker operation."""

    def failing_listener(signal: Signal) -> None:
        raise RuntimeError("listener failed")

    cb = CircuitBreaker(
        name="test",
        tripper=MinRequests(2) & FailureRate(0.5),
        listeners=[failing_listener],
    )

    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(failing_func)

    assert cb.info().state == StateEnum.OPEN.value


def test_decorator_with_fallback():
    """Decorator with fallback returns fallback value on exception."""
    cb = CircuitBreaker(name="test")

    @cb(fallback=lambda e: "fallback_value")
    def func() -> str:
        raise ValueError("error")

    assert func() == "fallback_value"


def test_fallback_receives_exception():
    """Fallback function receives the exception as argument."""
    cb = CircuitBreaker(name="test")
    received: list[Exception] = []

    def capture_fallback(e: Exception) -> str:
        received.append(e)
        return "captured"

    @cb(fallback=capture_fallback)
    def func() -> str:
        raise ValueError("specific error")

    func()
    assert len(received) == 1
    assert isinstance(received[0], ValueError)
    assert str(received[0]) == "specific error"


def test_fallback_can_reraise():
    """Fallback can re-raise the exception."""
    cb = CircuitBreaker(name="test")

    def selective_fallback(e: Exception) -> str:
        if isinstance(e, ValueError):
            return "handled"
        raise e

    @cb(fallback=selective_fallback)
    def func(error_type: type[Exception]) -> str:
        raise error_type("error")

    assert func(ValueError) == "handled"

    with pytest.raises(TypeError):
        func(TypeError)


def test_fallback_on_circuit_open():
    """Fallback is called when circuit is OPEN."""
    cb = CircuitBreaker(
        name="test",
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(10.0),
    )

    @cb
    def trip_func() -> None:
        raise ValueError("trip")

    for _ in range(2):
        with pytest.raises(ValueError):
            trip_func()

    @cb(fallback=lambda e: "circuit_open_fallback")
    def guarded_func() -> str:
        return "success"

    assert guarded_func() == "circuit_open_fallback"


def test_call_with_fallback():
    """call_with_fallback returns fallback value on exception."""
    cb = CircuitBreaker(name="test")

    result = cb.call_with_fallback(
        failing_func, lambda e: f"fallback: {type(e).__name__}"
    )
    assert result == "fallback: ValueError"


def test_call_with_fallback_passes_args():
    """call_with_fallback passes arguments to the function."""
    cb = CircuitBreaker(name="test")

    def add(a: int, b: int) -> int:
        return a + b

    result = cb.call_with_fallback(add, lambda e: 0, 3, 5)
    assert result == 8


def test_default_window_size_is_100():
    """Default window uses CountWindow(100) - tracks last 100 calls."""
    cb = CircuitBreaker(
        name="test",
        tripper=MinRequests(50) & FailureRate(0.5),
    )

    for _ in range(150):
        cb.call(success_func)

    assert cb.info().metrics.total_count == 100


def test_default_tripper_requires_100_requests():
    """Default tripper requires MinRequests(100) before tripping."""
    cb = CircuitBreaker(name="test")

    for _ in range(99):
        with pytest.raises(ValueError):
            cb.call(failing_func)

    assert cb.info().state == StateEnum.CLOSED.value

    with pytest.raises(ValueError):
        cb.call(failing_func)

    assert cb.info().state == StateEnum.OPEN.value


def test_default_tripper_50_percent_failure_rate():
    """Default tripper trips at 50% failure rate after 100 requests."""
    cb = CircuitBreaker(name="test")

    for _ in range(50):
        cb.call(success_func)

    for _ in range(49):
        with pytest.raises(ValueError):
            cb.call(failing_func)

    assert cb.info().state == StateEnum.CLOSED.value

    with pytest.raises(ValueError):
        cb.call(failing_func)

    assert cb.info().state == StateEnum.OPEN.value


def test_default_slow_threshold_is_60_seconds():
    """Default slow_threshold is 60.0 seconds."""
    cb = CircuitBreaker(name="test")

    cb.call(success_func)
    assert cb.info().metrics.slow_count == 0


def test_failure_streak_tripper():
    """FailureStreak tripper opens circuit after N consecutive failures."""
    cb = CircuitBreaker(
        name="test",
        tripper=FailureStreak(3),
    )

    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(failing_func)

    cb.call(success_func)
    assert cb.info().state == StateEnum.CLOSED.value

    for _ in range(3):
        with pytest.raises(ValueError):
            cb.call(failing_func)

    assert cb.info().state == StateEnum.OPEN.value


async def test_async_call_passes_through():
    """Successful async calls pass through when circuit is CLOSED."""
    cb = AsyncCircuitBreaker(name="test")

    assert await cb.call(async_success_func, 5) == 10
    assert await cb.call(async_success_func, 10) == 20

    info = cb.info()
    assert info.state == StateEnum.CLOSED.value
    assert info.metrics.total_count == 2


async def test_async_decorator_usage():
    """AsyncCircuitBreaker works as a decorator."""
    cb = AsyncCircuitBreaker(name="test")

    @cb
    async def decorated(x: int) -> int:
        return x + 1

    assert await decorated(5) == 6
    assert await decorated(10) == 11
    assert cb.info().metrics.total_count == 2


async def test_async_closed_to_open_on_failure_threshold():
    """Async circuit opens when failure rate exceeds threshold."""
    cb = AsyncCircuitBreaker(
        name="test",
        tripper=MinRequests(3) & FailureRate(0.5),
    )

    for _ in range(3):
        with pytest.raises(ValueError):
            await cb.call(async_failing_func)

    assert cb.info().state == StateEnum.OPEN.value


async def test_async_open_to_half_open_after_cooldown(freezer: FrozenDateTimeFactory):
    """Async circuit transitions to HALF_OPEN after cooldown period."""
    cb = AsyncCircuitBreaker(
        name="test",
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(60.0),
        permit=All(),
    )

    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(async_failing_func)

    freezer.tick(61)
    result = await cb.call(async_success_func)

    assert result == 2
    assert cb.info().state in [StateEnum.HALF_OPEN.value, StateEnum.CLOSED.value]


async def test_async_half_open_to_open_on_failure(freezer: FrozenDateTimeFactory):
    """Async circuit transitions from HALF_OPEN back to OPEN on failure."""
    cb = AsyncCircuitBreaker(
        name="test",
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(60.0),
        permit=All(),
    )

    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(async_failing_func)

    freezer.tick(61)
    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(async_failing_func)

    assert cb.info().state == StateEnum.OPEN.value


async def test_async_open_blocks_before_cooldown():
    """Async circuit blocks calls in OPEN state before cooldown expires."""
    cb = AsyncCircuitBreaker(
        name="test",
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(10.0),
    )

    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(async_failing_func)

    with pytest.raises(CallNotPermittedError):
        await cb.call(async_success_func)


async def test_async_half_open_permit_blocks_calls(freezer: FrozenDateTimeFactory):
    """Async permit can block calls in HALF_OPEN state."""
    cb = AsyncCircuitBreaker(
        name="test",
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(60.0),
        permit=Random(0.0),
    )

    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(async_failing_func)

    freezer.tick(61)
    with pytest.raises(CallNotPermittedError):
        await cb.call(async_success_func)


async def test_async_reset_transitions_to_closed():
    """Async reset() transitions circuit to CLOSED state."""
    cb = AsyncCircuitBreaker(
        name="test",
        tripper=MinRequests(2) & FailureRate(0.5),
    )

    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(async_failing_func)

    await cb.reset()
    assert cb.info().state == StateEnum.CLOSED.value


async def test_async_disable_and_force_open():
    """disable() and force_open() manually control async circuit state."""
    cb = AsyncCircuitBreaker(name="test")

    await cb.disable()
    assert cb.info().state == StateEnum.DISABLED.value

    with pytest.raises(ValueError):
        await cb.call(async_failing_func)

    await cb.force_open()
    assert cb.info().state == StateEnum.FORCED_OPEN.value

    with pytest.raises(CallNotPermittedError):
        await cb.call(async_success_func)


async def test_async_metrics_only_mode():
    """metrics_only() enables metric collection without circuit breaking."""
    cb = AsyncCircuitBreaker(
        name="test",
        tripper=MinRequests(2) & FailureRate(0.5),
    )

    await cb.metrics_only()

    for _ in range(5):
        with pytest.raises(ValueError):
            await cb.call(async_failing_func)

    info = cb.info()
    assert info.state == StateEnum.METRICS_ONLY.value
    assert info.metrics.failure_count == 5


async def test_async_untracked_exceptions_propagate():
    """Untracked exceptions propagate without affecting circuit state."""
    cb = AsyncCircuitBreaker(name="test", tracker=TypeOf(ValueError))

    async def raises_type_error() -> None:
        raise TypeError("not tracked")

    with pytest.raises(TypeError):
        await cb.call(raises_type_error)

    assert cb.info().metrics.failure_count == 0


async def test_async_half_open_untracked_exception_propagates(
    freezer: FrozenDateTimeFactory,
):
    """Untracked exceptions propagate in HALF_OPEN state without affecting circuit."""
    cb = AsyncCircuitBreaker(
        name="test",
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(60.0),
        permit=All(),
    )

    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(async_failing_func)

    async def raises_type_error() -> None:
        raise TypeError("not tracked")

    freezer.tick(61)
    with pytest.raises(TypeError):
        await cb.call(raises_type_error)

    assert cb.info().state == StateEnum.HALF_OPEN.value


async def test_async_listener_notification():
    """Async listeners are notified on state transitions."""
    notification_count = 0

    async def listener(signal: Signal) -> None:
        nonlocal notification_count
        notification_count += 1

    cb = AsyncCircuitBreaker(
        name="test",
        tripper=MinRequests(2) & FailureRate(0.5),
        listeners=[listener],
    )

    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(async_failing_func)

    assert notification_count == 1

    await cb.reset()
    assert notification_count == 2


async def test_async_listener_exception_handling():
    """Failing async listeners don't break circuit breaker operation."""

    async def failing_listener(signal: Signal) -> None:
        raise RuntimeError("listener failed")

    cb = AsyncCircuitBreaker(
        name="test",
        tripper=MinRequests(2) & FailureRate(0.5),
        listeners=[failing_listener],
    )

    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(async_failing_func)

    assert cb.info().state == StateEnum.OPEN.value


async def test_async_decorator_with_fallback():
    """Async decorator with fallback returns fallback value on exception."""
    cb = AsyncCircuitBreaker(name="test")

    @cb(fallback=lambda e: "fallback_value")
    async def func() -> str:
        raise ValueError("error")

    assert await func() == "fallback_value"


async def test_async_fallback_receives_exception():
    """Async fallback function receives the exception as argument."""
    cb = AsyncCircuitBreaker(name="test")
    received: list[Exception] = []

    def capture_fallback(e: Exception) -> str:
        received.append(e)
        return "captured"

    @cb(fallback=capture_fallback)
    async def func() -> str:
        raise ValueError("specific error")

    await func()
    assert len(received) == 1
    assert str(received[0]) == "specific error"


async def test_async_fallback_on_circuit_open():
    """Async fallback is called when circuit is OPEN."""
    cb = AsyncCircuitBreaker(
        name="test",
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(10.0),
    )

    @cb
    async def trip_func() -> None:
        raise ValueError("trip")

    for _ in range(2):
        with pytest.raises(ValueError):
            await trip_func()

    @cb(fallback=lambda e: "circuit_open_fallback")
    async def guarded_func() -> str:
        return "success"

    assert await guarded_func() == "circuit_open_fallback"


async def test_async_call_with_fallback():
    """async call_with_fallback returns fallback value on exception."""
    cb = AsyncCircuitBreaker(name="test")

    result = await cb.call_with_fallback(
        async_failing_func, lambda e: f"fallback: {type(e).__name__}"
    )
    assert result == "fallback: ValueError"


async def test_async_call_with_fallback_passes_args():
    """async call_with_fallback passes arguments to the function."""
    cb = AsyncCircuitBreaker(name="test")

    async def add(a: int, b: int) -> int:
        return a + b

    result = await cb.call_with_fallback(add, lambda e: 0, 3, 5)
    assert result == 8


async def test_async_default_tripper_requires_100_requests():
    """Async default tripper requires MinRequests(100) before tripping."""
    cb = AsyncCircuitBreaker(name="test")

    for _ in range(99):
        with pytest.raises(ValueError):
            await cb.call(async_failing_func)

    assert cb.info().state == StateEnum.CLOSED.value

    with pytest.raises(ValueError):
        await cb.call(async_failing_func)

    assert cb.info().state == StateEnum.OPEN.value


async def test_async_all_exception_types_tracked():
    """Async default tracker (All) tracks all exception types."""
    cb = AsyncCircuitBreaker(
        name="test",
        tripper=MinRequests(3) & FailureRate(0.5),
    )

    async def raise_value_error() -> None:
        raise ValueError("a")

    async def raise_type_error() -> None:
        raise TypeError("b")

    async def raise_runtime_error() -> None:
        raise RuntimeError("c")

    for func in [raise_value_error, raise_type_error, raise_runtime_error]:
        with pytest.raises(Exception):
            await cb.call(func)

    assert cb.info().state == StateEnum.OPEN.value


async def test_async_max_half_open_calls_limits_concurrency():
    """max_half_open_calls limits concurrent execution in HALF_OPEN state."""
    cb = AsyncCircuitBreaker(
        name="test",
        tripper=FailureStreak(1),
        retry=Cooldown(0.01),
        permit=All(),
        max_half_open_calls=2,
    )

    with pytest.raises(ValueError):
        await cb.call(async_failing_func)
    assert cb.info().state == StateEnum.OPEN.value

    await asyncio.sleep(0.02)

    max_concurrent = 0
    current_concurrent = 0
    lock = asyncio.Lock()
    semaphore_saturated = asyncio.Event()
    proceed = asyncio.Event()

    async def blocking_success() -> str:
        nonlocal max_concurrent, current_concurrent
        async with lock:
            current_concurrent += 1
            max_concurrent = max(max_concurrent, current_concurrent)
            if current_concurrent >= 2:
                semaphore_saturated.set()
        await proceed.wait()
        async with lock:
            current_concurrent -= 1
        return "ok"

    tasks = [asyncio.create_task(cb.call(blocking_success)) for _ in range(5)]

    await asyncio.wait_for(semaphore_saturated.wait(), timeout=1.0)
    await asyncio.sleep(0.05)

    assert cb.info().state == StateEnum.HALF_OPEN.value
    async with lock:
        assert current_concurrent == 2
        assert max_concurrent == 2

    proceed.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)

    successful = sum(1 for r in results if r == "ok")
    assert successful == 5
