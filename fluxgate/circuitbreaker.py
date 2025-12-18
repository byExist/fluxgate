from __future__ import annotations
import asyncio
import inspect
import logging
import time
import functools
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Awaitable, Callable, Iterable, ParamSpec, TypeVar, overload

from fluxgate.errors import CallNotPermittedError
from fluxgate.interfaces import (
    IListener,
    IAsyncListener,
    IPermit,
    ITripper,
    IRetry,
    IWindow,
    ITracker,
)
from fluxgate.metric import Record, Metric
from fluxgate.permits import RampUp
from fluxgate.retries import Cooldown
from fluxgate.signal import Signal
from fluxgate.state import StateEnum
from fluxgate.trackers import All
from fluxgate.trippers import FailureRate, MinRequests, SlowRate
from fluxgate.windows import CountWindow

__all__ = [
    "CircuitBreaker",
    "AsyncCircuitBreaker",
]

P = ParamSpec("P")
R = TypeVar("R")


@dataclass(frozen=True, slots=True)
class CircuitBreakerInfo:
    """Circuit breaker state information.

    Attributes:
        name: Circuit breaker name
        state: Current state (CLOSED, OPEN, HALF_OPEN, etc.)
        changed_at: Timestamp of last state change
        reopens: Number of times circuit reopened from HALF_OPEN to OPEN
        metrics: Aggregated metrics
    """

    name: str
    state: str
    changed_at: float
    reopens: int
    metrics: Metric


def _measure_duration(
    func: Callable[P, R], *args: P.args, **kwargs: P.kwargs
) -> tuple[R, float]:
    start_time = time.perf_counter()
    result = func(*args, **kwargs)
    end_time = time.perf_counter()
    return result, end_time - start_time


async def _async_measure_duration(
    func: Callable[P, Awaitable[R]], *args: P.args, **kwargs: P.kwargs
) -> tuple[R, float]:
    start_time = time.perf_counter()
    result = await func(*args, **kwargs)
    end_time = time.perf_counter()
    return result, end_time - start_time


class CircuitBreaker:
    """Synchronous circuit breaker implementation.

    Protects your service from cascading failures by monitoring call failures
    and temporarily blocking calls when a failure threshold is reached.

    The circuit breaker operates in three main states:

    - CLOSED: Normal operation, calls pass through
    - OPEN: Failure threshold exceeded, calls are blocked
    - HALF_OPEN: Testing if the service recovered, limited calls allowed

    Args:
        name: Circuit breaker identifier
        window: Sliding window for metrics collection (default: CountWindow(100))
        tracker: Determines which exceptions to track as failures (default: All())
        tripper: Condition to open/close the circuit based on metrics
            (default: MinRequests(100) & (FailureRate(0.5) | SlowRate(1.0)))
        retry: Strategy for transitioning from OPEN to HALF_OPEN (default: Cooldown(60.0))
        permit: Strategy for allowing calls in HALF_OPEN state (default: RampUp(0.0, 1.0, 60.0))
        slow_threshold: Duration threshold in seconds to mark calls as slow (default: 60.0)
        listeners: Event listeners for state transitions (default: empty)

    Examples:
        Basic usage with defaults:

        >>> cb = CircuitBreaker("my-service")
        >>> @cb
        ... def call_api():
        ...     return requests.get("https://api.example.com")

        Custom configuration:

        >>> cb = CircuitBreaker(
        ...     name="payment_api",
        ...     tracker=TypeOf(ConnectionError),
        ...     tripper=MinRequests(10) & FailureRate(0.5),
        ...     slow_threshold=1.0,
        ... )

    Note:
        This implementation is NOT thread-safe. Each process maintains its own
        independent circuit breaker state. For asyncio applications, use
        AsyncCircuitBreaker instead.
    """

    def __init__(
        self,
        name: str,
        window: IWindow | None = None,
        tracker: ITracker | None = None,
        tripper: ITripper | None = None,
        retry: IRetry | None = None,
        permit: IPermit | None = None,
        slow_threshold: float = 60.0,
        listeners: Iterable[IListener] = (),
    ) -> None:
        self._name = name
        self._window = window or CountWindow(100)
        self._tracker = tracker or All()
        self._tripper = tripper or MinRequests(100) & (FailureRate(0.5) | SlowRate(1.0))
        self._retry = retry or Cooldown(60.0)
        self._permit = permit or RampUp(0.0, 1.0, 60.0)
        self._listeners = tuple(listeners)
        self._slow_threshold = slow_threshold
        self._changed_at = time.time()
        self._reopens = 0
        self._consecutive_failures = 0
        self._state: CircuitBreaker._State = self._Closed(self)

    class _State(ABC):
        def __init__(self, cb: CircuitBreaker) -> None:
            self.cb = cb

        @abstractmethod
        def get_state_enum(self) -> StateEnum:
            pass

        @abstractmethod
        def execute(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
            pass

    class _Closed(_State):
        def get_state_enum(self) -> StateEnum:
            return StateEnum.CLOSED

        def execute(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
            try:
                result, duration = _measure_duration(func, *args, **kwargs)
                is_slow = duration > self.cb._slow_threshold
                self.cb._window.record(
                    Record(success=True, duration=duration, is_slow=is_slow)
                )
                self.cb._consecutive_failures = 0
                return result
            except Exception as e:
                if not self.cb._tracker(e):
                    raise e
                self.cb._consecutive_failures += 1
                self.cb._window.record(Record(success=False))
                metric = self.cb._window.get_metric()
                if self.cb._tripper(
                    metric, StateEnum.CLOSED, self.cb._consecutive_failures
                ):
                    self.cb._transition_to(StateEnum.OPEN)
                raise e

    class _Open(_State):
        def get_state_enum(self) -> StateEnum:
            return StateEnum.OPEN

        def execute(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
            if not self.cb._retry(self.cb._changed_at, self.cb._reopens):
                raise CallNotPermittedError("Circuit breaker is open")
            self.cb._transition_to(StateEnum.HALF_OPEN)
            return self.cb._state.execute(func, *args, **kwargs)

    class _HalfOpen(_State):
        def get_state_enum(self) -> StateEnum:
            return StateEnum.HALF_OPEN

        def execute(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
            if not self.cb._permit(self.cb._changed_at):
                raise CallNotPermittedError(
                    "Circuit breaker is half-open, not executing"
                )
            try:
                result, duration = _measure_duration(func, *args, **kwargs)
                is_slow = duration > self.cb._slow_threshold
                self.cb._window.record(
                    Record(success=True, duration=duration, is_slow=is_slow)
                )
                self.cb._consecutive_failures = 0
                metric = self.cb._window.get_metric()
                if not self.cb._tripper(
                    metric, StateEnum.HALF_OPEN, self.cb._consecutive_failures
                ):
                    self.cb._transition_to(StateEnum.CLOSED)
                return result
            except Exception as e:
                if not self.cb._tracker(e):
                    raise e
                self.cb._consecutive_failures += 1
                self.cb._window.record(Record(success=False))
                metric = self.cb._window.get_metric()
                if self.cb._tripper(
                    metric, StateEnum.HALF_OPEN, self.cb._consecutive_failures
                ):
                    self.cb._transition_to(StateEnum.OPEN)
                raise e

    class _MetricsOnly(_State):
        def get_state_enum(self) -> StateEnum:
            return StateEnum.METRICS_ONLY

        def execute(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
            try:
                result, duration = _measure_duration(func, *args, **kwargs)
                is_slow = duration > self.cb._slow_threshold
                self.cb._window.record(
                    Record(success=True, duration=duration, is_slow=is_slow)
                )
                self.cb._consecutive_failures = 0
                return result
            except Exception as e:
                if not self.cb._tracker(e):
                    raise e
                self.cb._consecutive_failures += 1
                self.cb._window.record(Record(success=False))
                raise e

    class _Disabled(_State):
        def get_state_enum(self) -> StateEnum:
            return StateEnum.DISABLED

        def execute(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
            return func(*args, **kwargs)

    class _ForcedOpen(_State):
        def get_state_enum(self) -> StateEnum:
            return StateEnum.FORCED_OPEN

        def execute(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
            raise CallNotPermittedError("Circuit breaker is forced open")

    @overload
    def __call__(self, func: Callable[P, R]) -> Callable[P, R]: ...

    @overload
    def __call__(
        self,
        func: None = None,
        *,
        fallback: Callable[[Exception], R] | None = None,
    ) -> Callable[[Callable[P, R]], Callable[P, R]]: ...

    def __call__(
        self,
        func: Callable[P, R] | None = None,
        *,
        fallback: Callable[[Exception], R] | None = None,
    ) -> Callable[P, R] | Callable[[Callable[P, R]], Callable[P, R]]:
        """Decorate a function with circuit breaker protection.

        Examples:
            >>> @cb
            ... def api_call():
            ...     return requests.get("https://api.example.com")

            >>> @cb(fallback=lambda e: cached_value)
            ... def api_call():
            ...     return requests.get("https://api.example.com")

        Args:
            func: Function to protect
            fallback: Optional function to call on exception. Receives the exception
                as argument and should return a fallback value or re-raise.

        Returns:
            Wrapped function with circuit breaker behavior

        Raises:
            CallNotPermittedError: When circuit is OPEN or FORCED_OPEN (if no fallback)
        """

        def decorator(f: Callable[P, R]) -> Callable[P, R]:
            @functools.wraps(f)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                try:
                    return self._state.execute(f, *args, **kwargs)
                except Exception as e:
                    if fallback is not None:
                        return fallback(e)
                    raise

            return wrapper

        if func is not None:
            return decorator(func)
        return decorator

    def call(
        self,
        func: Callable[P, R],
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        """Execute a function with circuit breaker protection.

        Examples:
            >>> cb.call(requests.get, "https://api.example.com")

        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Function result

        Raises:
            CallNotPermittedError: When circuit is OPEN or FORCED_OPEN
        """
        return self._state.execute(func, *args, **kwargs)

    def call_with_fallback(
        self,
        func: Callable[P, R],
        fallback: Callable[[Exception], R],
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        """Execute a function with circuit breaker protection and fallback.

        Examples:
            >>> cb.call_with_fallback(fetch_data, lambda e: cached_data)

        Args:
            func: Function to execute
            fallback: Function to call on exception. Receives the exception
                as argument and should return a fallback value or re-raise.
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Function result or fallback result
        """
        try:
            return self._state.execute(func, *args, **kwargs)
        except Exception as e:
            return fallback(e)

    def info(self) -> CircuitBreakerInfo:
        """Get current circuit breaker state and metrics.

        Returns:
            Dictionary with circuit breaker state information
        """
        return CircuitBreakerInfo(
            name=self._name,
            state=self._state.get_state_enum().value,
            changed_at=self._changed_at,
            reopens=self._reopens,
            metrics=self._window.get_metric(),
        )

    def reset(self) -> None:
        """Reset circuit breaker to CLOSED state and clear metrics."""
        current_state = self._state.get_state_enum()
        self._state = self._Closed(self)
        self._changed_at = time.time()
        self._reopens = 0
        self._consecutive_failures = 0
        self._window.reset()

        signal = Signal(
            circuit_name=self._name,
            old_state=current_state,
            new_state=StateEnum.CLOSED,
            timestamp=self._changed_at,
        )
        self._notify(signal)

    def disable(self) -> None:
        """Disable circuit breaker (all calls pass through without tracking)."""
        self._transition_to(StateEnum.DISABLED)

    def metrics_only(self) -> None:
        """Enable metrics-only mode (track metrics but never open circuit)."""
        self._transition_to(StateEnum.METRICS_ONLY)

    def force_open(self) -> None:
        """Force circuit breaker to OPEN state (all calls blocked)."""
        self._transition_to(StateEnum.FORCED_OPEN)

    def _transition_to(self, state: StateEnum) -> None:
        current_state = self._state.get_state_enum()

        if state == StateEnum.OPEN and current_state == StateEnum.HALF_OPEN:
            self._reopens += 1
        elif state == StateEnum.CLOSED:
            self._reopens = 0
            self._consecutive_failures = 0

        if state == StateEnum.CLOSED:
            self._state = self._Closed(self)
        elif state == StateEnum.OPEN:
            self._state = self._Open(self)
        elif state == StateEnum.HALF_OPEN:
            self._state = self._HalfOpen(self)
        elif state == StateEnum.METRICS_ONLY:
            self._state = self._MetricsOnly(self)
        elif state == StateEnum.DISABLED:
            self._state = self._Disabled(self)
        else:
            self._state = self._ForcedOpen(self)

        self._changed_at = time.time()
        self._window.reset()

        signal = Signal(
            circuit_name=self._name,
            old_state=current_state,
            new_state=state,
            timestamp=self._changed_at,
        )
        self._notify(signal)

    def _notify(self, signal: Signal) -> None:
        for listener in self._listeners:
            try:
                listener(signal)
            except Exception:
                logging.exception(f"Listener {listener.__class__.__name__} failed")


class AsyncCircuitBreaker:
    """Asynchronous circuit breaker implementation for asyncio applications.

    Thread-safe circuit breaker with async/await support. Uses asyncio locks
    to coordinate state transitions and metric updates across concurrent tasks.

    The circuit breaker operates in three main states:

    - CLOSED: Normal operation, calls pass through
    - OPEN: Failure threshold exceeded, calls are blocked
    - HALF_OPEN: Testing if the service recovered, limited calls allowed

    Args:
        name: Circuit breaker identifier
        window: Sliding window for metrics collection (default: CountWindow(100))
        tracker: Determines which exceptions to track as failures (default: All())
        tripper: Condition to open/close the circuit based on metrics
            (default: MinRequests(100) & (FailureRate(0.5) | SlowRate(1.0)))
        retry: Strategy for transitioning from OPEN to HALF_OPEN (default: Cooldown(60.0))
        permit: Strategy for allowing calls in HALF_OPEN state (default: RampUp(0.0, 1.0, 60.0))
        slow_threshold: Duration threshold in seconds to mark calls as slow (default: 60.0)
        max_half_open_calls: Maximum concurrent calls allowed in HALF_OPEN state (default: 10)
        listeners: Event listeners for state transitions (default: empty)

    Examples:
        Basic usage with defaults:

        >>> cb = AsyncCircuitBreaker("my-service")
        >>> @cb
        ... async def call_api():
        ...     async with httpx.AsyncClient() as client:
        ...         return await client.get("https://api.example.com")

        Custom configuration:

        >>> cb = AsyncCircuitBreaker(
        ...     name="payment_api",
        ...     tracker=TypeOf(httpx.ConnectError),
        ...     tripper=MinRequests(10) & FailureRate(0.5),
        ...     slow_threshold=1.0,
        ... )

    Note:
        Uses asyncio locks for thread safety within a single event loop.
        Each process maintains its own independent circuit breaker state.
    """

    def __init__(
        self,
        name: str,
        window: IWindow | None = None,
        tracker: ITracker | None = None,
        tripper: ITripper | None = None,
        retry: IRetry | None = None,
        permit: IPermit | None = None,
        slow_threshold: float = 60.0,
        max_half_open_calls: int = 10,
        listeners: Iterable[IListener | IAsyncListener] = (),
    ) -> None:
        self._name = name
        self._window = window or CountWindow(100)
        self._tracker = tracker or All()
        self._tripper = tripper or MinRequests(100) & (FailureRate(0.5) | SlowRate(1.0))
        self._retry = retry or Cooldown(60.0)
        self._permit = permit or RampUp(0.0, 1.0, 60.0)
        self._listeners = tuple(listeners)
        self._slow_threshold = slow_threshold
        self._changed_at = time.time()
        self._reopens = 0
        self._consecutive_failures = 0
        self._state: AsyncCircuitBreaker._State = self._Closed(self)
        self._state_lock = asyncio.Lock()
        self._half_open_semaphore = asyncio.Semaphore(max_half_open_calls)
        self._window_lock = asyncio.Lock()

    class _State(ABC):
        def __init__(self, cb: AsyncCircuitBreaker) -> None:
            self.cb = cb

        @abstractmethod
        def get_state_enum(self) -> StateEnum:
            pass

        @abstractmethod
        async def execute(
            self,
            func: Callable[P, Awaitable[R]],
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:
            pass

    class _Closed(_State):
        def get_state_enum(self) -> StateEnum:
            return StateEnum.CLOSED

        async def execute(
            self,
            func: Callable[P, Awaitable[R]],
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:
            try:
                result, duration = await _async_measure_duration(func, *args, **kwargs)
                is_slow = duration > self.cb._slow_threshold
                async with self.cb._window_lock:
                    self.cb._window.record(
                        Record(success=True, duration=duration, is_slow=is_slow)
                    )
                    self.cb._consecutive_failures = 0
                return result
            except Exception as e:
                if not self.cb._tracker(e):
                    raise e
                async with self.cb._window_lock:
                    self.cb._consecutive_failures += 1
                    self.cb._window.record(Record(success=False))
                    metric = self.cb._window.get_metric()
                await self.cb._try_transition_to_open(metric, StateEnum.CLOSED)
                raise e

    class _Open(_State):
        def get_state_enum(self) -> StateEnum:
            return StateEnum.OPEN

        async def execute(
            self,
            func: Callable[P, Awaitable[R]],
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:
            if not self.cb._retry(self.cb._changed_at, self.cb._reopens):
                raise CallNotPermittedError("Circuit breaker is open")
            await self.cb._try_transition_to_half_open()
            return await self.cb._state.execute(func, *args, **kwargs)

    class _HalfOpen(_State):
        def get_state_enum(self) -> StateEnum:
            return StateEnum.HALF_OPEN

        async def execute(
            self,
            func: Callable[P, Awaitable[R]],
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:
            async with self.cb._half_open_semaphore:
                if self.cb._state.get_state_enum() != StateEnum.HALF_OPEN:
                    return await self.cb._state.execute(func, *args, **kwargs)
                if not self.cb._permit(self.cb._changed_at):
                    raise CallNotPermittedError(
                        "Circuit breaker is half-open, not executing"
                    )
                try:
                    result, duration = await _async_measure_duration(
                        func, *args, **kwargs
                    )
                    is_slow = duration > self.cb._slow_threshold
                    async with self.cb._window_lock:
                        self.cb._window.record(
                            Record(success=True, duration=duration, is_slow=is_slow)
                        )
                        self.cb._consecutive_failures = 0
                        metric = self.cb._window.get_metric()
                    await self.cb._try_transition_to_closed(metric)
                    return result
                except Exception as e:
                    if not self.cb._tracker(e):
                        raise e
                    async with self.cb._window_lock:
                        self.cb._consecutive_failures += 1
                        self.cb._window.record(Record(success=False))
                        metric = self.cb._window.get_metric()
                    await self.cb._try_transition_to_open(metric, StateEnum.HALF_OPEN)
                    raise e

    class _MetricsOnly(_State):
        def get_state_enum(self) -> StateEnum:
            return StateEnum.METRICS_ONLY

        async def execute(
            self,
            func: Callable[P, Awaitable[R]],
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:
            try:
                result, duration = await _async_measure_duration(func, *args, **kwargs)
                is_slow = duration > self.cb._slow_threshold
                async with self.cb._window_lock:
                    self.cb._window.record(
                        Record(success=True, duration=duration, is_slow=is_slow)
                    )
                    self.cb._consecutive_failures = 0
                return result
            except Exception as e:
                if not self.cb._tracker(e):
                    raise e
                async with self.cb._window_lock:
                    self.cb._consecutive_failures += 1
                    self.cb._window.record(Record(success=False))
                raise e

    class _Disabled(_State):
        def get_state_enum(self) -> StateEnum:
            return StateEnum.DISABLED

        async def execute(
            self,
            func: Callable[P, Awaitable[R]],
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:
            return await func(*args, **kwargs)

    class _ForcedOpen(_State):
        def get_state_enum(self) -> StateEnum:
            return StateEnum.FORCED_OPEN

        async def execute(
            self,
            func: Callable[P, Awaitable[R]],
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:
            raise CallNotPermittedError("Circuit breaker is forced open")

    @overload
    def __call__(
        self, func: Callable[P, Awaitable[R]]
    ) -> Callable[P, Awaitable[R]]: ...

    @overload
    def __call__(
        self,
        func: None = None,
        *,
        fallback: Callable[[Exception], R] | None = None,
    ) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]: ...

    def __call__(
        self,
        func: Callable[P, Awaitable[R]] | None = None,
        *,
        fallback: Callable[[Exception], R] | None = None,
    ) -> (
        Callable[P, Awaitable[R]]
        | Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]
    ):
        """Decorate an awaitable function with circuit breaker protection.

        Examples:
            >>> @cb
            ... async def api_call():
            ...     async with httpx.AsyncClient() as client:
            ...         return await client.get("https://api.example.com")

            >>> @cb(fallback=lambda e: cached_value)
            ... async def api_call():
            ...     return await fetch_data()

        Args:
            func: Awaitable function to protect
            fallback: Optional function to call on exception. Receives the exception
                as argument and should return a fallback value or re-raise.

        Returns:
            Wrapped awaitable function with circuit breaker behavior

        Raises:
            CallNotPermittedError: When circuit is OPEN or FORCED_OPEN (if no fallback)
        """

        def decorator(
            f: Callable[P, Awaitable[R]],
        ) -> Callable[P, Awaitable[R]]:
            @functools.wraps(f)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                try:
                    return await self._state.execute(f, *args, **kwargs)
                except Exception as e:
                    if fallback is not None:
                        return fallback(e)
                    raise

            return wrapper

        if func is not None:
            return decorator(func)
        return decorator

    async def call(
        self,
        func: Callable[P, Awaitable[R]],
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        """Execute an awaitable function with circuit breaker protection.

        Examples:
            >>> await cb.call(client.get, "https://api.example.com")

        Args:
            func: Awaitable function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Function result

        Raises:
            CallNotPermittedError: When circuit is OPEN or FORCED_OPEN
        """
        return await self._state.execute(func, *args, **kwargs)

    async def call_with_fallback(
        self,
        func: Callable[P, Awaitable[R]],
        fallback: Callable[[Exception], R],
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        """Execute an awaitable function with circuit breaker protection and fallback.

        Examples:
            >>> await cb.call_with_fallback(fetch_data, lambda e: cached_data)

        Args:
            func: Awaitable function to execute
            fallback: Function to call on exception. Receives the exception
                as argument and should return a fallback value or re-raise.
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Function result or fallback result
        """
        try:
            return await self._state.execute(func, *args, **kwargs)
        except Exception as e:
            return fallback(e)

    def info(self) -> CircuitBreakerInfo:
        """Get current circuit breaker state and metrics.

        Returns:
            Dictionary with circuit breaker state information
        """
        return CircuitBreakerInfo(
            name=self._name,
            state=self._state.get_state_enum().value,
            changed_at=self._changed_at,
            reopens=self._reopens,
            metrics=self._window.get_metric(),
        )

    async def reset(self) -> None:
        """Reset circuit breaker to CLOSED state and clear metrics."""
        async with self._state_lock:
            await self._transition_to(StateEnum.CLOSED)

    async def disable(self) -> None:
        """Disable circuit breaker (all calls pass through without tracking)."""
        async with self._state_lock:
            await self._transition_to(StateEnum.DISABLED)

    async def metrics_only(self) -> None:
        """Enable metrics-only mode (track metrics but never open circuit)."""
        async with self._state_lock:
            await self._transition_to(StateEnum.METRICS_ONLY)

    async def force_open(self) -> None:
        """Force circuit breaker to OPEN state (all calls blocked)."""
        async with self._state_lock:
            await self._transition_to(StateEnum.FORCED_OPEN)

    async def _try_transition_to_open(
        self, metric: Metric, from_state: StateEnum
    ) -> bool:
        async with self._state_lock:
            current_state = self._state.get_state_enum()
            if current_state != from_state:
                return False
            if not self._tripper(metric, current_state, self._consecutive_failures):
                return False
            await self._transition_to(StateEnum.OPEN)
            return True

    async def _try_transition_to_half_open(self) -> bool:
        async with self._state_lock:
            current_state = self._state.get_state_enum()
            if current_state != StateEnum.OPEN:
                return False
            await self._transition_to(StateEnum.HALF_OPEN)
            return True

    async def _try_transition_to_closed(self, metric: Metric) -> bool:
        async with self._state_lock:
            current_state = self._state.get_state_enum()
            if current_state != StateEnum.HALF_OPEN:
                return False
            if self._tripper(metric, current_state, self._consecutive_failures):
                return False
            await self._transition_to(StateEnum.CLOSED)
            return True

    async def _transition_to(self, state: StateEnum) -> None:
        current_state = self._state.get_state_enum()

        if state == StateEnum.OPEN and current_state == StateEnum.HALF_OPEN:
            self._reopens += 1
        elif state == StateEnum.CLOSED:
            self._reopens = 0
            self._consecutive_failures = 0

        if state == StateEnum.CLOSED:
            self._state = self._Closed(self)
        elif state == StateEnum.OPEN:
            self._state = self._Open(self)
        elif state == StateEnum.HALF_OPEN:
            self._state = self._HalfOpen(self)
        elif state == StateEnum.METRICS_ONLY:
            self._state = self._MetricsOnly(self)
        elif state == StateEnum.DISABLED:
            self._state = self._Disabled(self)
        else:
            self._state = self._ForcedOpen(self)

        self._changed_at = time.time()
        async with self._window_lock:
            self._window.reset()

        signal = Signal(
            circuit_name=self._name,
            old_state=current_state,
            new_state=state,
            timestamp=self._changed_at,
        )
        await self._notify(signal)

    async def _notify(self, signal: Signal) -> None:
        async def _safe_call(listener: IListener | IAsyncListener) -> None:
            try:
                if inspect.iscoroutinefunction(listener):
                    await listener(signal)
                else:
                    listener(signal)
            except Exception:
                logging.exception(f"Listener {listener.__class__.__name__} failed")

        await asyncio.gather(*[_safe_call(listener) for listener in self._listeners])
