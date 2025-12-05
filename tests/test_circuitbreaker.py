"""Tests for CircuitBreaker (sync and async) - integration tests."""

import asyncio
import time

import pytest

from fluxgate import (
    CircuitBreaker,
    AsyncCircuitBreaker,
    CallNotPermittedError,
    StateEnum,
)
from fluxgate.signal import Signal
from fluxgate.windows import CountWindow
from fluxgate.trackers import TypeOf
from fluxgate.trippers import MinRequests, FailureRate, FailureStreak
from fluxgate.retries import Cooldown
from fluxgate.permits import Random


def test_successful_calls_in_closed_state():
    """Successful calls pass through when circuit is CLOSED."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(5) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    def success_func(x: int):
        return x * 2

    # Call multiple times
    assert cb.call(success_func, 5) == 10
    assert cb.call(success_func, 10) == 20

    # Check state
    info = cb.info()
    assert info.state == StateEnum.CLOSED.value
    assert info.metrics.total_count == 2
    assert info.metrics.failure_count == 0


def test_decorator_usage():
    """CircuitBreaker works as a decorator."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(5) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    @cb
    def decorated_func(x: int):
        return x + 1

    assert decorated_func(5) == 6
    assert decorated_func(10) == 11

    info = cb.info()
    assert info.metrics.total_count == 2


def test_untracked_exceptions_propagate():
    """Exceptions not tracked by tracker are propagated without recording."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(5) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    def raises_untracked():
        raise TypeError("not tracked")

    try:
        cb.call(raises_untracked)
        assert False, "Should have raised TypeError"
    except TypeError as e:
        assert str(e) == "not tracked"

    # Should not be recorded in metrics
    info = cb.info()
    assert info.metrics.total_count == 0
    assert info.metrics.failure_count == 0


def test_closed_to_open_on_failure_threshold():
    """Circuit opens when failure rate exceeds threshold."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(3) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    def failing_func() -> None:
        raise ValueError("fail")

    # Call until threshold reached (3 calls, 100% failure rate)
    for _ in range(3):
        try:
            cb.call(failing_func)
        except ValueError:
            pass

    # Circuit should now be OPEN
    info = cb.info()
    assert info.state == StateEnum.OPEN.value
    # Metrics reset on state transition
    assert info.metrics.total_count == 0


def test_open_state_blocks_calls():
    """Circuit blocks calls with CallNotPermittedError when OPEN."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=10.0),  # Long cooldown
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    def failing_func() -> None:
        raise ValueError("fail")

    # Trip the circuit
    for _ in range(2):
        try:
            cb.call(failing_func)
        except ValueError:
            pass

    # Now calls should be blocked
    def any_func() -> str:
        return "success"

    try:
        cb.call(any_func)
        assert False, "Should have raised CallNotPermittedError"
    except CallNotPermittedError:
        pass  # Expected


def test_open_to_half_open_after_cooldown():
    """Circuit transitions to HALF_OPEN after cooldown period."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=0.05),  # Very short cooldown for test
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    def failing_func() -> None:
        raise ValueError("fail")

    # Trip the circuit
    for _ in range(2):
        try:
            cb.call(failing_func)
        except ValueError:
            pass

    assert cb.info().state == StateEnum.OPEN.value

    # Wait for cooldown
    time.sleep(0.06)

    # Next call should trigger transition to HALF_OPEN and potentially CLOSED
    def success_func():
        return "ok"

    result = cb.call(success_func)
    assert result == "ok"

    # After successful call, may transition to CLOSED immediately
    # (depends on tripper logic in HALF_OPEN state)
    info = cb.info()
    assert info.state in [StateEnum.HALF_OPEN.value, StateEnum.CLOSED.value]


def test_half_open_to_closed_on_success():
    """Circuit closes after successful calls in HALF_OPEN state."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=0.05),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    def failing_func() -> None:
        raise ValueError("fail")

    def success_func():
        return "ok"

    # Trip the circuit
    for _ in range(2):
        try:
            cb.call(failing_func)
        except ValueError:
            pass

    # Wait and recover
    time.sleep(0.06)

    # Make enough successful calls to close the circuit
    # tripper checks MinRequests(2) & FailureRate(0.5)
    # In HALF_OPEN, need enough successes to not trip
    for _ in range(3):
        cb.call(success_func)

    # Should be CLOSED now
    info = cb.info()
    assert info.state == StateEnum.CLOSED.value


def test_half_open_to_open_on_failure():
    """Circuit reopens if failures continue in HALF_OPEN state."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=0.05),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    def failing_func() -> None:
        raise ValueError("fail")

    # Trip the circuit first time
    for _ in range(2):
        try:
            cb.call(failing_func)
        except ValueError:
            pass

    initial_reopens = cb.info().reopens

    # Wait for transition to HALF_OPEN
    time.sleep(0.06)

    # Fail again in HALF_OPEN
    for _ in range(2):
        try:
            cb.call(failing_func)
        except ValueError:
            pass

    # Should be OPEN again with reopens incremented
    info = cb.info()
    assert info.state == StateEnum.OPEN.value
    assert info.reopens == initial_reopens + 1


def test_half_open_permit_blocks_calls():
    """Calls blocked by permit in HALF_OPEN state raise CallNotPermittedError."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=0.05),
        permit=Random(ratio=0.0),  # Never permit
        listeners=[],
        slow_threshold=1.0,
    )

    def failing_func() -> None:
        raise ValueError("fail")

    # Trip the circuit
    for _ in range(2):
        try:
            cb.call(failing_func)
        except ValueError:
            pass

    # Wait for transition to HALF_OPEN
    time.sleep(0.06)

    def success_func():
        return "ok"

    # Permit should block all calls in HALF_OPEN
    try:
        cb.call(success_func)
        assert False, "Should have raised CallNotPermittedError"
    except CallNotPermittedError:
        pass


def test_half_open_untracked_exception_propagates():
    """Untracked exceptions in HALF_OPEN propagate without state change."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=0.05),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    def failing_func() -> None:
        raise ValueError("fail")

    # Trip the circuit
    for _ in range(2):
        try:
            cb.call(failing_func)
        except ValueError:
            pass

    # Wait for transition to HALF_OPEN
    time.sleep(0.06)

    def raises_untracked():
        raise TypeError("not tracked")

    # Untracked exception should propagate
    try:
        cb.call(raises_untracked)
        assert False, "Should have raised TypeError"
    except TypeError as e:
        assert str(e) == "not tracked"

    # Should remain in HALF_OPEN
    info = cb.info()
    assert info.state == StateEnum.HALF_OPEN.value


def test_manual_reset():
    """reset() transitions circuit to CLOSED state."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=10.0),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    # Trip the circuit
    def failing_func() -> None:
        raise ValueError("fail")

    for _ in range(2):
        try:
            cb.call(failing_func)
        except ValueError:
            pass

    assert cb.info().state == StateEnum.OPEN.value

    # Manual reset
    cb.reset()

    # Should be CLOSED now
    assert cb.info().state == StateEnum.CLOSED.value


def test_listener_notification():
    """Listeners are notified on state transitions."""
    notification_count = 0

    def listener(signal: Signal):
        nonlocal notification_count
        notification_count += 1

    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[listener],
        slow_threshold=1.0,
    )

    def failing_func() -> None:
        raise ValueError("fail")

    # Trip the circuit (will notify CLOSED->OPEN)
    for _ in range(2):
        try:
            cb.call(failing_func)
        except ValueError:
            pass

    assert cb.info().state == StateEnum.OPEN.value
    assert notification_count == 1

    # Reset with notification
    cb.reset(notify=True)
    assert cb.info().state == StateEnum.CLOSED.value
    assert notification_count == 2


def test_listener_exception_handling():
    """Failing listeners don't break circuit breaker operation."""

    def failing_listener(signal: Signal):
        raise RuntimeError("listener failed")

    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[failing_listener],
        slow_threshold=1.0,
    )

    def failing_func() -> None:
        raise ValueError("fail")

    # Trip the circuit - listener exception should be caught
    for _ in range(2):
        try:
            cb.call(failing_func)
        except ValueError:
            pass

    assert cb.info().state == StateEnum.OPEN.value


def test_state_transitions_skip_notification():
    """State transitions can skip listener notification with notify=False."""
    notification_count = 0

    def listener(signal: Signal):
        nonlocal notification_count
        notification_count += 1

    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[listener],
        slow_threshold=1.0,
    )

    # All state transitions with notify=False
    cb.reset(notify=False)
    assert notification_count == 0

    cb.disable(notify=False)
    assert notification_count == 0

    cb.metrics_only(notify=False)
    assert notification_count == 0

    cb.force_open(notify=False)
    assert notification_count == 0


def test_metrics_only_mode():
    """metrics_only() enables metric collection without circuit breaking."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    # Enable metrics-only mode
    cb.metrics_only()
    assert cb.info().state == StateEnum.METRICS_ONLY.value

    def failing_func() -> None:
        raise ValueError("fail")

    def success_func():
        return "ok"

    # Failures should be tracked but not trip the circuit
    for _ in range(5):
        try:
            cb.call(failing_func)
        except ValueError:
            pass

    # Metrics should be collected
    info = cb.info()
    assert info.state == StateEnum.METRICS_ONLY.value
    assert info.metrics.failure_count == 5

    # Successful calls should also be tracked
    cb.call(success_func)
    info = cb.info()
    assert info.metrics.total_count == 6
    assert info.metrics.failure_count == 5

    # Untracked exceptions should propagate
    def raises_untracked():
        raise TypeError("not tracked")

    try:
        cb.call(raises_untracked)
        assert False, "Should have raised TypeError"
    except TypeError:
        pass


def test_manual_disable_and_force_open():
    """disable() and force_open() manually control circuit state."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(5) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    # Disable the circuit
    cb.disable()
    assert cb.info().state == StateEnum.DISABLED.value

    # Calls should pass through even with failures
    def failing_func() -> None:
        raise ValueError("fail")

    try:
        cb.call(failing_func)
    except ValueError:
        pass  # Exception propagates but circuit stays DISABLED

    assert cb.info().state == StateEnum.DISABLED.value

    # Force open
    cb.force_open()
    assert cb.info().state == StateEnum.FORCED_OPEN.value

    # Calls should be blocked
    def success_func():
        return "ok"

    try:
        cb.call(success_func)
        assert False, "Should have raised CallNotPermittedError"
    except CallNotPermittedError:
        pass


async def test_async_successful_calls_in_closed_state():
    """Successful async calls pass through when circuit is CLOSED."""
    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(5) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
        max_half_open_calls=5,
    )

    async def success_func(x: int):
        return x * 2

    assert await cb.call(success_func, 5) == 10
    assert await cb.call(success_func, 10) == 20

    info = cb.info()
    assert info.state == StateEnum.CLOSED.value
    assert info.metrics.total_count == 2
    assert info.metrics.failure_count == 0


async def test_async_decorator_usage():
    """AsyncCircuitBreaker works as a decorator."""
    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(5) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
        max_half_open_calls=5,
    )

    @cb
    async def decorated_func(x: int):
        return x + 1

    assert await decorated_func(5) == 6
    assert await decorated_func(10) == 11

    info = cb.info()
    assert info.metrics.total_count == 2


async def test_async_closed_to_open_on_failure_threshold():
    """Async circuit opens when failure rate exceeds threshold."""
    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(3) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
        max_half_open_calls=5,
    )

    async def failing_func():
        raise ValueError("fail")

    for _ in range(3):
        try:
            await cb.call(failing_func)
        except ValueError:
            pass

    info = cb.info()
    assert info.state == StateEnum.OPEN.value
    assert info.metrics.total_count == 0


async def test_async_open_to_half_open_after_cooldown():
    """Async circuit transitions to HALF_OPEN after cooldown period."""
    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=0.05),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
        max_half_open_calls=5,
    )

    async def failing_func():
        raise ValueError("fail")

    for _ in range(2):
        try:
            await cb.call(failing_func)
        except ValueError:
            pass

    assert cb.info().state == StateEnum.OPEN.value

    await asyncio.sleep(0.06)

    async def success_func():
        return "ok"

    result = await cb.call(success_func)
    assert result == "ok"

    info = cb.info()
    assert info.state in [StateEnum.HALF_OPEN.value, StateEnum.CLOSED.value]


async def test_async_half_open_to_open_on_failure():
    """Async circuit transitions from HALF_OPEN back to OPEN on failure."""
    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=0.05),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
        max_half_open_calls=5,
    )

    async def failing_func():
        raise ValueError("fail")

    for _ in range(2):
        try:
            await cb.call(failing_func)
        except ValueError:
            pass

    assert cb.info().state == StateEnum.OPEN.value

    await asyncio.sleep(0.06)

    for _ in range(2):
        try:
            await cb.call(failing_func)
        except ValueError:
            pass

    assert cb.info().state == StateEnum.OPEN.value


async def test_async_half_open_untracked_exception_propagates():
    """Untracked exceptions propagate in HALF_OPEN state without affecting circuit."""
    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=0.05),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
        max_half_open_calls=5,
    )

    async def failing_func():
        raise ValueError("fail")

    for _ in range(2):
        try:
            await cb.call(failing_func)
        except ValueError:
            pass

    assert cb.info().state == StateEnum.OPEN.value

    await asyncio.sleep(0.06)

    async def raises_untracked():
        raise TypeError("not tracked")

    try:
        await cb.call(raises_untracked)
        assert False, "Should have raised TypeError"
    except TypeError:
        pass

    # Circuit should remain in HALF_OPEN, not affected by untracked exception
    assert cb.info().state == StateEnum.HALF_OPEN.value


async def test_async_half_open_permit_blocks_calls():
    """Async permit can block calls in HALF_OPEN state."""
    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=0.05),
        permit=Random(ratio=0.0),
        listeners=[],
        slow_threshold=1.0,
        max_half_open_calls=5,
    )

    async def failing_func():
        raise ValueError("fail")

    for _ in range(2):
        try:
            await cb.call(failing_func)
        except ValueError:
            pass

    assert cb.info().state == StateEnum.OPEN.value

    await asyncio.sleep(0.06)

    async def success_func():
        return "ok"

    try:
        await cb.call(success_func)
        assert False, "Should have raised CallNotPermittedError"
    except CallNotPermittedError:
        pass


async def test_async_open_blocks_before_cooldown():
    """Async circuit blocks calls in OPEN state before cooldown expires."""
    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=1.0),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
        max_half_open_calls=5,
    )

    async def failing_func():
        raise ValueError("fail")

    for _ in range(2):
        try:
            await cb.call(failing_func)
        except ValueError:
            pass

    assert cb.info().state == StateEnum.OPEN.value

    async def success_func():
        return "ok"

    try:
        await cb.call(success_func)
        assert False, "Should have raised CallNotPermittedError"
    except CallNotPermittedError:
        pass


async def test_async_manual_reset():
    """Async reset() transitions circuit to CLOSED state."""
    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=10.0),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
        max_half_open_calls=5,
    )

    async def failing_func():
        raise ValueError("fail")

    for _ in range(2):
        try:
            await cb.call(failing_func)
        except ValueError:
            pass

    assert cb.info().state == StateEnum.OPEN.value

    await cb.reset()

    assert cb.info().state == StateEnum.CLOSED.value


async def test_async_concurrent_calls_in_half_open():
    """max_half_open_calls limits concurrent execution in HALF_OPEN state."""
    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(10) & FailureRate(0.5),
        retry=Cooldown(duration=0.05),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
        max_half_open_calls=2,
    )

    async def failing_func():
        raise ValueError("fail")

    for _ in range(10):
        try:
            await cb.call(failing_func)
        except ValueError:
            pass

    await asyncio.sleep(0.06)

    max_concurrent = 0
    current_concurrent = 0
    lock = asyncio.Lock()

    async def slow_success():
        nonlocal max_concurrent, current_concurrent
        async with lock:
            current_concurrent += 1
            max_concurrent = max(max_concurrent, current_concurrent)
        await asyncio.sleep(0.05)
        async with lock:
            current_concurrent -= 1
        return "ok"

    tasks = [asyncio.create_task(cb.call(slow_success)) for _ in range(5)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    successful = sum(1 for r in results if r == "ok")
    assert successful == 5
    assert max_concurrent <= 2


async def test_async_untracked_exceptions_propagate():
    """Untracked exceptions propagate without affecting circuit state."""
    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
        max_half_open_calls=5,
    )

    async def raises_untracked():
        raise TypeError("not tracked")

    try:
        await cb.call(raises_untracked)
        assert False, "Should have raised TypeError"
    except TypeError:
        pass

    info = cb.info()
    assert info.state == StateEnum.CLOSED.value
    assert info.metrics.failure_count == 0


async def test_async_metrics_only_mode():
    """metrics_only() enables metric collection without circuit breaking."""
    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
        max_half_open_calls=5,
    )

    await cb.metrics_only()
    assert cb.info().state == StateEnum.METRICS_ONLY.value

    async def failing_func():
        raise ValueError("fail")

    async def success_func():
        return "ok"

    for _ in range(5):
        try:
            await cb.call(failing_func)
        except ValueError:
            pass

    info = cb.info()
    assert info.state == StateEnum.METRICS_ONLY.value
    assert info.metrics.failure_count == 5

    await cb.call(success_func)
    info = cb.info()
    assert info.metrics.total_count == 6
    assert info.metrics.failure_count == 5

    async def raises_untracked():
        raise TypeError("not tracked")

    try:
        await cb.call(raises_untracked)
        assert False, "Should have raised TypeError"
    except TypeError:
        pass


async def test_async_race_condition_state_change():
    """Async state transitions handle race conditions correctly."""
    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=100),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(10) & FailureRate(0.5),
        retry=Cooldown(duration=0.05),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
        max_half_open_calls=3,
    )

    async def failing_func():
        await asyncio.sleep(0.01)
        raise ValueError("fail")

    async def success_func():
        await asyncio.sleep(0.01)
        return "ok"

    # Trip the circuit
    tasks = [asyncio.create_task(cb.call(failing_func)) for _ in range(10)]
    await asyncio.gather(*tasks, return_exceptions=True)
    assert cb.info().state == StateEnum.OPEN.value

    # Wait for cooldown
    await asyncio.sleep(0.06)

    # Multiple concurrent calls in HALF_OPEN - some will succeed, triggering CLOSED
    tasks = [asyncio.create_task(cb.call(success_func)) for _ in range(5)]
    await asyncio.gather(*tasks, return_exceptions=True)

    # Circuit should transition to CLOSED or remain in HALF_OPEN
    state = cb.info().state
    assert state in [StateEnum.HALF_OPEN.value, StateEnum.CLOSED.value]


async def test_async_manual_disable_and_force_open():
    """disable() and force_open() manually control async circuit state."""
    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(5) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
        max_half_open_calls=5,
    )

    async def failing_func():
        raise ValueError("fail")

    await cb.disable()
    assert cb.info().state == StateEnum.DISABLED.value

    try:
        await cb.call(failing_func)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

    await cb.force_open()
    assert cb.info().state == StateEnum.FORCED_OPEN.value

    async def success_func():
        return "ok"

    try:
        await cb.call(success_func)
        assert False, "Should have raised CallNotPermittedError"
    except CallNotPermittedError:
        pass


async def test_async_listener_notification():
    """Async listeners are notified on state transitions."""
    notification_count = 0

    async def listener(signal: Signal):
        nonlocal notification_count
        notification_count += 1

    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[listener],
        slow_threshold=1.0,
        max_half_open_calls=5,
    )

    async def failing_func():
        raise ValueError("fail")

    for _ in range(2):
        try:
            await cb.call(failing_func)
        except ValueError:
            pass

    assert cb.info().state == StateEnum.OPEN.value
    assert notification_count == 1

    await cb.reset()
    assert cb.info().state == StateEnum.CLOSED.value
    assert notification_count == 2


async def test_async_listener_exception_handling():
    """Failing async listeners don't break circuit breaker operation."""

    async def failing_listener(signal: Signal):
        raise RuntimeError("listener failed")

    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[failing_listener],
        slow_threshold=1.0,
        max_half_open_calls=5,
    )

    async def failing_func():
        raise ValueError("fail")

    for _ in range(2):
        try:
            await cb.call(failing_func)
        except ValueError:
            pass

    assert cb.info().state == StateEnum.OPEN.value


# Fallback tests for sync CircuitBreaker


def test_decorator_with_fallback():
    """Decorator with fallback returns fallback value on exception."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(5) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    @cb(fallback=lambda e: "fallback_value")
    def failing_func():
        raise ValueError("error")

    result = failing_func()
    assert result == "fallback_value"


def test_decorator_fallback_receives_exception():
    """Fallback function receives the exception as argument."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(5) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    received_exception: Exception | None = None

    def capture_fallback(e: Exception) -> str:
        nonlocal received_exception
        received_exception = e
        return "captured"

    @cb(fallback=capture_fallback)
    def failing_func() -> str:
        raise ValueError("specific error")

    result = failing_func()
    assert result == "captured"
    assert isinstance(received_exception, ValueError)
    assert str(received_exception) == "specific error"


def test_decorator_fallback_can_reraise():
    """Fallback can re-raise the exception."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(5) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    def selective_fallback(e: Exception) -> str:
        if isinstance(e, ValueError):
            return "handled"
        raise e

    @cb(fallback=selective_fallback)
    def failing_func(error_type: type[Exception]) -> str:
        raise error_type("error")

    assert failing_func(ValueError) == "handled"

    with pytest.raises(TypeError):
        failing_func(TypeError)


def test_decorator_fallback_on_circuit_open():
    """Fallback is called when circuit is OPEN."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=10.0),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    # Trip the circuit first
    @cb
    def trip_func():
        raise ValueError("trip")

    for _ in range(2):
        try:
            trip_func()
        except ValueError:
            pass

    assert cb.info().state == StateEnum.OPEN.value

    # Now use fallback decorator
    @cb(fallback=lambda e: "circuit_open_fallback")
    def guarded_func():
        return "success"

    result = guarded_func()
    assert result == "circuit_open_fallback"


def test_call_with_fallback():
    """call_with_fallback returns fallback value on exception."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(5) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    def failing_func():
        raise RuntimeError("error")

    result = cb.call_with_fallback(
        failing_func, lambda e: f"fallback: {type(e).__name__}"
    )
    assert result == "fallback: RuntimeError"


def test_call_with_fallback_passes_args():
    """call_with_fallback passes arguments to the function."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(5) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    def add(a: int, b: int) -> int:
        return a + b

    result = cb.call_with_fallback(add, lambda e: 0, 3, 5)
    assert result == 8


# Fallback tests for async AsyncCircuitBreaker


async def test_async_decorator_with_fallback():
    """Async decorator with fallback returns fallback value on exception."""
    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(5) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    @cb(fallback=lambda e: "fallback_value")
    async def failing_func():
        raise ValueError("error")

    result = await failing_func()
    assert result == "fallback_value"


async def test_async_decorator_fallback_receives_exception():
    """Async fallback function receives the exception as argument."""
    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(5) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    received_exception: Exception | None = None

    def capture_fallback(e: Exception) -> str:
        nonlocal received_exception
        received_exception = e
        return "captured"

    @cb(fallback=capture_fallback)
    async def failing_func() -> str:
        raise ValueError("specific error")

    result = await failing_func()
    assert result == "captured"
    assert isinstance(received_exception, ValueError)
    assert str(received_exception) == "specific error"


async def test_async_decorator_fallback_on_circuit_open():
    """Async fallback is called when circuit is OPEN."""
    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(2) & FailureRate(0.5),
        retry=Cooldown(duration=10.0),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    # Trip the circuit first
    @cb
    async def trip_func():
        raise ValueError("trip")

    for _ in range(2):
        try:
            await trip_func()
        except ValueError:
            pass

    assert cb.info().state == StateEnum.OPEN.value

    # Now use fallback decorator
    @cb(fallback=lambda e: "circuit_open_fallback")
    async def guarded_func():
        return "success"

    result = await guarded_func()
    assert result == "circuit_open_fallback"


async def test_async_call_with_fallback():
    """async call_with_fallback returns fallback value on exception."""
    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(5) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    async def failing_func():
        raise RuntimeError("error")

    result = await cb.call_with_fallback(
        failing_func, lambda e: f"fallback: {type(e).__name__}"
    )
    assert result == "fallback: RuntimeError"


async def test_async_call_with_fallback_passes_args():
    """async call_with_fallback passes arguments to the function."""
    cb = AsyncCircuitBreaker(
        name="test",
        window=CountWindow(size=10),
        tracker=TypeOf(ValueError),
        tripper=MinRequests(5) & FailureRate(0.5),
        retry=Cooldown(duration=0.1),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    async def add(a: int, b: int) -> int:
        return a + b

    result = await cb.call_with_fallback(add, lambda e: 0, 3, 5)
    assert result == 8


def test_failure_streak_trips_circuit():
    """FailureStreak tripper opens circuit after N consecutive failures."""
    cb = CircuitBreaker(
        name="test",
        window=CountWindow(size=100),
        tracker=TypeOf(ValueError),
        tripper=FailureStreak(3),
        retry=Cooldown(duration=10.0),
        permit=Random(ratio=1.0),
        listeners=[],
        slow_threshold=1.0,
    )

    def failing_func():
        raise ValueError("fail")

    def success_func():
        return "ok"

    # First 2 failures - should not trip
    for _ in range(2):
        try:
            cb.call(failing_func)
        except ValueError:
            pass
    assert cb.info().state == StateEnum.CLOSED.value

    # Success resets counter
    cb.call(success_func)

    # 2 more failures - should not trip (counter was reset)
    for _ in range(2):
        try:
            cb.call(failing_func)
        except ValueError:
            pass
    assert cb.info().state == StateEnum.CLOSED.value

    # 3rd consecutive failure - should trip
    try:
        cb.call(failing_func)
    except ValueError:
        pass
    assert cb.info().state == StateEnum.OPEN.value
