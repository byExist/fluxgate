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
from fluxgate.listeners import AsyncListener, Listener
from fluxgate.metric import Record, Metric
from fluxgate.permits import Permit, RampUp
from fluxgate.retries import Cooldown, Retry
from fluxgate.signal import Signal
from fluxgate.state import State
from fluxgate.trackers import All, Tracker
from fluxgate.trippers import CallContext, FailureRate, MinRequests, SlowRate, Tripper
from fluxgate.windows import CountWindow, Window

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
        state: Current state (CLOSED, OPEN, HALF_OPEN, etc.)
        changed_at: Timestamp of last state change
        reopens: Number of times circuit reopened from HALF_OPEN to OPEN
        metrics: Aggregated metrics
    """

    state: State
    changed_at: float
    reopens: int
    metrics: Metric


def _collect_slow_thresholds(tripper: Tripper) -> tuple[float, ...]:
    """Walk a tripper tree and collect all SlowRate thresholds, deduplicated.

    Any tripper subclassing ``Tripper`` is iterable (leaves yield themselves;
    composites yield from children). Trippers that aren't iterable contribute
    nothing.
    """
    try:
        nodes = iter(tripper)
    except TypeError:
        return ()
    seen: set[float] = set()
    for node in nodes:
        if isinstance(node, SlowRate):
            seen.add(node.threshold)
    return tuple(sorted(seen))


def _classify_slow(duration: float, thresholds: tuple[float, ...]) -> tuple[float, ...]:
    """Return the thresholds the call exceeded, preserving registration order."""
    return tuple(t for t in thresholds if duration >= t)


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
        window: Sliding window for metrics collection (default: CountWindow(100))
        tracker: Determines which exceptions to track as failures (default: All())
        tripper: Condition to open/close the circuit based on metrics
            (default: MinRequests(100) & FailureRate(0.5))
        retry: Strategy for transitioning from OPEN to HALF_OPEN (default: Cooldown(60.0))
        permit: Strategy for allowing calls in HALF_OPEN state (default: RampUp(0.0, 1.0, 60.0))
        listeners: Event listeners for state transitions (default: empty)

    Examples:
        Basic usage with defaults:

        >>> cb = CircuitBreaker()
        >>> @cb
        ... def call_api():
        ...     return requests.get("https://api.example.com")

        Custom configuration with slow-call detection:

        >>> cb = CircuitBreaker(
        ...     tracker=TypeOf(ConnectionError),
        ...     tripper=MinRequests(10) & (FailureRate(0.5) | SlowRate(0.3, threshold=1.0)),
        ... )

    Note:
        This implementation is NOT thread-safe. Each process maintains its own
        independent circuit breaker state. For asyncio applications, use
        AsyncCircuitBreaker instead.
    """

    def __init__(
        self,
        window: Window | None = None,
        tracker: Tracker | None = None,
        tripper: Tripper | None = None,
        retry: Retry | None = None,
        permit: Permit | None = None,
        listeners: Iterable[Listener] = (),
    ) -> None:
        self._window = window or CountWindow(100)
        self._tracker = tracker or All()
        self._tripper = tripper or MinRequests(100) & FailureRate(0.5)
        self._retry = retry or Cooldown(60.0)
        self._permit = permit or RampUp(0.0, 1.0, 60.0)
        self._listeners = tuple(listeners)
        self._slow_thresholds = _collect_slow_thresholds(self._tripper)
        self._changed_at = time.time()
        self._reopens = 0
        self._consecutive_failures = 0
        self._handlers: dict[State, CircuitBreaker._Handler] = {
            "closed": self._Closed(self),
            "open": self._Open(self),
            "half_open": self._HalfOpen(self),
            "metrics_only": self._MetricsOnly(self),
            "disabled": self._Disabled(self),
            "forced_open": self._ForcedOpen(self),
        }
        self._state: CircuitBreaker._Handler = self._handlers["closed"]

    class _Handler(ABC):
        state: State

        def __init__(self, cb: CircuitBreaker) -> None:
            self.cb = cb

        @abstractmethod
        def execute(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
            pass

    class _Closed(_Handler):
        state: State = "closed"

        def execute(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
            try:
                result, duration = _measure_duration(func, *args, **kwargs)
                self.cb._record_success(duration)
                if self.cb._tripper(
                    CallContext(
                        metric=self.cb._window.get_metric(),
                        state="closed",
                        consecutive_failures=self.cb._consecutive_failures,
                    )
                ):
                    self.cb._transition_to("open")
                return result
            except Exception as e:
                if not self.cb._tracker(e):
                    raise e
                self.cb._record_failure()
                metric = self.cb._window.get_metric()
                if self.cb._tripper(
                    CallContext(
                        metric=metric,
                        state="closed",
                        consecutive_failures=self.cb._consecutive_failures,
                    )
                ):
                    self.cb._transition_to("open")
                raise e

    class _Open(_Handler):
        state: State = "open"

        def execute(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
            if not self.cb._retry(self.cb._changed_at, self.cb._reopens):
                raise CallNotPermittedError("Circuit breaker is open")
            self.cb._transition_to("half_open")
            return self.cb._state.execute(func, *args, **kwargs)

    class _HalfOpen(_Handler):
        state: State = "half_open"

        def execute(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
            if not self.cb._permit(self.cb._changed_at):
                raise CallNotPermittedError(
                    "Circuit breaker is half-open, not executing"
                )
            try:
                result, duration = _measure_duration(func, *args, **kwargs)
                self.cb._record_success(duration)
                metric = self.cb._window.get_metric()
                if not self.cb._tripper(
                    CallContext(
                        metric=metric,
                        state="half_open",
                        consecutive_failures=self.cb._consecutive_failures,
                    )
                ):
                    self.cb._transition_to("closed")
                return result
            except Exception as e:
                if not self.cb._tracker(e):
                    raise e
                self.cb._record_failure()
                metric = self.cb._window.get_metric()
                if self.cb._tripper(
                    CallContext(
                        metric=metric,
                        state="half_open",
                        consecutive_failures=self.cb._consecutive_failures,
                    )
                ):
                    self.cb._transition_to("open")
                raise e

    class _MetricsOnly(_Handler):
        state: State = "metrics_only"

        def execute(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
            try:
                result, duration = _measure_duration(func, *args, **kwargs)
                self.cb._record_success(duration)
                return result
            except Exception as e:
                if not self.cb._tracker(e):
                    raise e
                self.cb._record_failure()
                raise e

    class _Disabled(_Handler):
        state: State = "disabled"

        def execute(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
            return func(*args, **kwargs)

    class _ForcedOpen(_Handler):
        state: State = "forced_open"

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
            state=self._state.state,
            changed_at=self._changed_at,
            reopens=self._reopens,
            metrics=self._window.get_metric(),
        )

    def reset(self) -> None:
        """Reset circuit breaker to CLOSED state and clear metrics."""
        self._transition_to("closed")

    def disable(self) -> None:
        """Disable circuit breaker (all calls pass through without tracking)."""
        self._transition_to("disabled")

    def metrics_only(self) -> None:
        """Enable metrics-only mode (track metrics but never open circuit)."""
        self._transition_to("metrics_only")

    def force_open(self) -> None:
        """Force circuit breaker to OPEN state (all calls blocked)."""
        self._transition_to("forced_open")

    def _record_success(self, duration: float) -> None:
        """Record a successful call."""
        self._window.record(
            Record(
                success=True,
                duration=duration,
                slow_at=_classify_slow(duration, self._slow_thresholds),
            )
        )
        self._consecutive_failures = 0

    def _record_failure(self) -> None:
        """Record a failed call."""
        self._consecutive_failures += 1
        self._window.record(Record(success=False))

    def _transition_to(self, state: State) -> None:
        current_state = self._state.state

        if state == "open" and current_state == "half_open":
            self._reopens += 1
        elif state == "closed":
            self._reopens = 0
            self._consecutive_failures = 0

        self._state = self._handlers[state]
        self._changed_at = time.time()
        self._window.reset()

        signal = Signal(
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

    Coordinates concurrent calls within a single event loop using one
    ``asyncio.Lock`` for all internal state mutations, plus an
    ``asyncio.Semaphore`` to cap concurrent HALF_OPEN trial calls.

    The circuit breaker operates in three main states:

    - CLOSED: Normal operation, calls pass through
    - OPEN: Failure threshold exceeded, calls are blocked
    - HALF_OPEN: Testing if the service recovered, limited calls allowed

    Args:
        window: Sliding window for metrics collection (default: CountWindow(100))
        tracker: Determines which exceptions to track as failures (default: All())
        tripper: Condition to open/close the circuit based on metrics
            (default: MinRequests(100) & FailureRate(0.5))
        retry: Strategy for transitioning from OPEN to HALF_OPEN (default: Cooldown(60.0))
        permit: Strategy for allowing calls in HALF_OPEN state (default: RampUp(0.0, 1.0, 60.0))
        max_half_open_calls: Maximum concurrent calls allowed in HALF_OPEN state (default: 10)
        listeners: Event listeners for state transitions (default: empty)

    Examples:
        Basic usage with defaults:

        >>> cb = AsyncCircuitBreaker()
        >>> @cb
        ... async def call_api():
        ...     async with httpx.AsyncClient() as client:
        ...         return await client.get("https://api.example.com")

        Custom configuration with slow-call detection:

        >>> cb = AsyncCircuitBreaker(
        ...     tracker=TypeOf(httpx.ConnectError),
        ...     tripper=MinRequests(10) & (FailureRate(0.5) | SlowRate(0.3, threshold=1.0)),
        ... )

    Concurrency model:
        All state mutations (window record, counter updates, state
        transitions) happen under a single ``asyncio.Lock``. The protected
        callable and listener notifications run outside the lock, so the
        critical section is small and ``await`` never holds the lock.

        Each call captures its handler on entry. When its outcome is
        applied, the handler checks ``self is cb._state`` and discards the
        outcome if the state has changed in the meantime, so a transition
        cannot pollute the next state's metric window. The only race that
        slips through is a regression back to the same handler instance
        (e.g. ``closed → open → half_open → closed``); since the window is
        reset on every transition, at most one stale sample may then land
        in the new window. Pair small windows with ``MinRequests`` if a
        single stale sample could flip your tripper.

    Note:
        Each process maintains its own independent circuit breaker state.
    """

    def __init__(
        self,
        window: Window | None = None,
        tracker: Tracker | None = None,
        tripper: Tripper | None = None,
        retry: Retry | None = None,
        permit: Permit | None = None,
        max_half_open_calls: int = 10,
        listeners: Iterable[Listener | AsyncListener] = (),
    ) -> None:
        self._window = window or CountWindow(100)
        self._tracker = tracker or All()
        self._tripper = tripper or MinRequests(100) & FailureRate(0.5)
        self._retry = retry or Cooldown(60.0)
        self._permit = permit or RampUp(0.0, 1.0, 60.0)
        self._listeners = tuple(listeners)
        self._slow_thresholds = _collect_slow_thresholds(self._tripper)
        self._changed_at = time.time()
        self._reopens = 0
        self._consecutive_failures = 0
        self._handlers: dict[State, AsyncCircuitBreaker._Handler] = {
            "closed": self._Closed(self),
            "open": self._Open(self),
            "half_open": self._HalfOpen(self),
            "metrics_only": self._MetricsOnly(self),
            "disabled": self._Disabled(self),
            "forced_open": self._ForcedOpen(self),
        }
        self._state: AsyncCircuitBreaker._Handler = self._handlers["closed"]
        self._lock = asyncio.Lock()
        self._half_open_semaphore = asyncio.Semaphore(max_half_open_calls)

    class _Handler(ABC):
        state: State

        def __init__(self, cb: AsyncCircuitBreaker) -> None:
            self.cb = cb

        @abstractmethod
        async def execute(
            self,
            func: Callable[P, Awaitable[R]],
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:
            pass

    class _Closed(_Handler):
        state: State = "closed"

        async def execute(
            self,
            func: Callable[P, Awaitable[R]],
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:
            try:
                result, duration = await _async_measure_duration(func, *args, **kwargs)
            except Exception as e:
                if not self.cb._tracker(e):
                    raise
                async with self.cb._lock:
                    if self.cb._state is self:
                        self.cb._record_failure()
                        if self.cb._tripper(
                            CallContext(
                                metric=self.cb._window.get_metric(),
                                state="closed",
                                consecutive_failures=self.cb._consecutive_failures,
                            )
                        ):
                            signal = self.cb._transition_to("open")
                        else:
                            signal = None
                    else:
                        signal = None
                if signal is not None:
                    await self.cb._notify(signal)
                raise
            async with self.cb._lock:
                if self.cb._state is self:
                    self.cb._record_success(duration)
                    if self.cb._tripper(
                        CallContext(
                            metric=self.cb._window.get_metric(),
                            state="closed",
                            consecutive_failures=self.cb._consecutive_failures,
                        )
                    ):
                        signal = self.cb._transition_to("open")
                    else:
                        signal = None
                else:
                    signal = None
            if signal is not None:
                await self.cb._notify(signal)
            return result

    class _Open(_Handler):
        state: State = "open"

        async def execute(
            self,
            func: Callable[P, Awaitable[R]],
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:
            async with self.cb._lock:
                if self.cb._state is self:
                    if not self.cb._retry(self.cb._changed_at, self.cb._reopens):
                        raise CallNotPermittedError("Circuit breaker is open")
                    signal = self.cb._transition_to("half_open")
                else:
                    signal = None
            if signal is not None:
                await self.cb._notify(signal)
            return await self.cb._state.execute(func, *args, **kwargs)

    class _HalfOpen(_Handler):
        state: State = "half_open"

        async def execute(
            self,
            func: Callable[P, Awaitable[R]],
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:
            async with self.cb._half_open_semaphore:
                if self.cb._state is not self:
                    return await self.cb._state.execute(func, *args, **kwargs)
                if not self.cb._permit(self.cb._changed_at):
                    raise CallNotPermittedError(
                        "Circuit breaker is half-open, not executing"
                    )
                try:
                    result, duration = await _async_measure_duration(
                        func, *args, **kwargs
                    )
                except Exception as e:
                    if not self.cb._tracker(e):
                        raise
                    async with self.cb._lock:
                        if self.cb._state is self:
                            self.cb._record_failure()
                            if self.cb._tripper(
                                CallContext(
                                    metric=self.cb._window.get_metric(),
                                    state="half_open",
                                    consecutive_failures=self.cb._consecutive_failures,
                                )
                            ):
                                signal = self.cb._transition_to("open")
                            else:
                                signal = None
                        else:
                            signal = None
                    if signal is not None:
                        await self.cb._notify(signal)
                    raise
                async with self.cb._lock:
                    if self.cb._state is self:
                        self.cb._record_success(duration)
                        if not self.cb._tripper(
                            CallContext(
                                metric=self.cb._window.get_metric(),
                                state="half_open",
                                consecutive_failures=self.cb._consecutive_failures,
                            )
                        ):
                            signal = self.cb._transition_to("closed")
                        else:
                            signal = None
                    else:
                        signal = None
                if signal is not None:
                    await self.cb._notify(signal)
                return result

    class _MetricsOnly(_Handler):
        state: State = "metrics_only"

        async def execute(
            self,
            func: Callable[P, Awaitable[R]],
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:
            try:
                result, duration = await _async_measure_duration(func, *args, **kwargs)
            except Exception as e:
                if self.cb._tracker(e):
                    async with self.cb._lock:
                        if self.cb._state is self:
                            self.cb._record_failure()
                raise
            async with self.cb._lock:
                if self.cb._state is self:
                    self.cb._record_success(duration)
            return result

    class _Disabled(_Handler):
        state: State = "disabled"

        async def execute(
            self,
            func: Callable[P, Awaitable[R]],
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:
            return await func(*args, **kwargs)

    class _ForcedOpen(_Handler):
        state: State = "forced_open"

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
            state=self._state.state,
            changed_at=self._changed_at,
            reopens=self._reopens,
            metrics=self._window.get_metric(),
        )

    async def reset(self) -> None:
        """Reset circuit breaker to CLOSED state and clear metrics."""
        await self._command("closed")

    async def disable(self) -> None:
        """Disable circuit breaker (all calls pass through without tracking)."""
        await self._command("disabled")

    async def metrics_only(self) -> None:
        """Enable metrics-only mode (track metrics but never open circuit)."""
        await self._command("metrics_only")

    async def force_open(self) -> None:
        """Force circuit breaker to OPEN state (all calls blocked)."""
        await self._command("forced_open")

    async def _command(self, target: State) -> None:
        async with self._lock:
            signal = self._transition_to(target)
        await self._notify(signal)

    def _record_success(self, duration: float) -> None:
        """Record a successful call. Caller must hold ``_lock``."""
        self._window.record(
            Record(
                success=True,
                duration=duration,
                slow_at=_classify_slow(duration, self._slow_thresholds),
            )
        )
        self._consecutive_failures = 0

    def _record_failure(self) -> None:
        """Record a failed call. Caller must hold ``_lock``."""
        self._consecutive_failures += 1
        self._window.record(Record(success=False))

    def _transition_to(self, state: State) -> Signal:
        """Apply a state transition. Caller must hold ``_lock`` and
        ``_notify`` the returned signal *outside* the lock.
        """
        current_state = self._state.state

        if state == "open" and current_state == "half_open":
            self._reopens += 1
        elif state == "closed":
            self._reopens = 0
            self._consecutive_failures = 0

        self._state = self._handlers[state]
        self._changed_at = time.time()
        self._window.reset()

        return Signal(
            old_state=current_state,
            new_state=state,
            timestamp=self._changed_at,
        )

    async def _notify(self, signal: Signal) -> None:
        async def _safe_call(listener: Listener | AsyncListener) -> None:
            try:
                result = listener(signal)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logging.exception(f"Listener {listener.__class__.__name__} failed")

        await asyncio.gather(*[_safe_call(listener) for listener in self._listeners])
