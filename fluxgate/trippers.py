"""Tripper conditions for determining when to open/close the circuit."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator

from fluxgate.metric import Metric
from fluxgate.state import State

__all__ = [
    "CallContext",
    "Tripper",
    "Closed",
    "HalfOpened",
    "MinRequests",
    "FailureRate",
    "AvgLatency",
    "SlowRate",
    "FailureStreak",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class CallContext:
    """Snapshot passed to trippers on each evaluation.

    Carries the window-derived :class:`Metric` together with the breaker's
    immediate state and consecutive failure count.
    """

    metric: Metric
    state: State
    consecutive_failures: int


class Tripper(ABC):
    """Base class for tripper conditions.

    Subclasses must override ``__call__``. Composite trippers (``_And``/``_Or``)
    override ``__iter__`` to expose their children; a leaf yields itself by
    default. The ``&`` and ``|`` operators build composite trippers.
    """

    @abstractmethod
    def __call__(self, ctx: CallContext) -> bool: ...

    def __iter__(self) -> Iterator[Tripper]:
        yield self

    def __and__(self, other: Tripper) -> Tripper:
        return _And(self, other)

    def __or__(self, other: Tripper) -> Tripper:
        return _Or(self, other)


class _And(Tripper):
    def __init__(self, lhs: Tripper, rhs: Tripper) -> None:
        self._lhs, self._rhs = lhs, rhs

    def __call__(self, ctx: CallContext) -> bool:
        return self._lhs(ctx) and self._rhs(ctx)

    def __iter__(self) -> Iterator[Tripper]:
        yield from self._lhs
        yield from self._rhs


class _Or(Tripper):
    def __init__(self, lhs: Tripper, rhs: Tripper) -> None:
        self._lhs, self._rhs = lhs, rhs

    def __call__(self, ctx: CallContext) -> bool:
        return self._lhs(ctx) or self._rhs(ctx)

    def __iter__(self) -> Iterator[Tripper]:
        yield from self._lhs
        yield from self._rhs


class Closed(Tripper):
    """Tripper that returns true only when circuit is in CLOSED state.

    Used to compose conditions that should only apply when circuit is closed.

    Examples:
        >>> # Only check failure rate when circuit is closed
        >>> tripper = Closed() & FailureRate(0.5)
    """

    def __call__(self, ctx: CallContext) -> bool:
        return ctx.state == "closed"


class HalfOpened(Tripper):
    """Tripper that returns true only when circuit is in HALF_OPEN state.

    Used to compose conditions that should only apply when circuit is half-open.

    Examples:
        >>> # Only check failure rate when circuit is half-open
        >>> tripper = HalfOpened() & FailureRate(0.3)
    """

    def __call__(self, ctx: CallContext) -> bool:
        return ctx.state == "half_open"


class MinRequests(Tripper):
    """Tripper that requires minimum number of calls before evaluating.

    Prevents premature circuit opening when sample size is too small.

    Examples:
        >>> # Only trip after at least 10 calls
        >>> tripper = MinRequests(10) & FailureRate(0.5)

    Args:
        count: Minimum number of calls required
    """

    def __init__(self, count: int) -> None:
        if count <= 0:
            raise ValueError("Count must be greater than zero")
        self._count = count

    def __call__(self, ctx: CallContext) -> bool:
        return ctx.metric.total_count >= self._count


class FailureRate(Tripper):
    """Tripper based on failure rate threshold.

    Returns true when the ratio of failed calls exceeds the threshold.

    Examples:
        >>> # Trip when 50% or more calls fail
        >>> tripper = FailureRate(0.5)

    Args:
        ratio: Failure rate threshold (0.0 to 1.0)
    """

    def __init__(self, ratio: float) -> None:
        if ratio <= 0 or ratio > 1:
            raise ValueError("Ratio must be between 0 and 1")
        self._ratio = ratio

    def __call__(self, ctx: CallContext) -> bool:
        if ctx.metric.total_count == 0:
            return False
        failure_rate = ctx.metric.failure_count / ctx.metric.total_count
        return failure_rate >= self._ratio


class AvgLatency(Tripper):
    """Tripper based on average latency threshold.

    Returns true when average call duration reaches or exceeds the threshold.

    Examples:
        >>> # Trip when average latency reaches 2 seconds
        >>> tripper = AvgLatency(2.0)

    Args:
        threshold: Latency threshold in seconds
    """

    def __init__(self, threshold: float) -> None:
        if threshold <= 0:
            raise ValueError("Threshold must be greater than 0")
        self._threshold = threshold

    def __call__(self, ctx: CallContext) -> bool:
        if ctx.metric.total_count == 0:
            return False
        avg_duration = ctx.metric.total_duration / ctx.metric.total_count
        return avg_duration >= self._threshold


class SlowRate(Tripper):
    """Tripper based on slow call rate against a duration threshold.

    A call is "slow" when its duration is at least ``threshold`` seconds.
    The tripper fires when the ratio of slow calls in the current window
    reaches ``ratio``. Several ``SlowRate`` instances with different
    thresholds can coexist in the same tripper tree — the circuit breaker
    walks the tree and registers each threshold with the window.

    Examples:
        >>> # Trip when 30% of calls take 1s or longer.
        >>> tripper = SlowRate(0.3, threshold=1.0)
        >>>
        >>> # Combine layered thresholds for tiered alerts.
        >>> tripper = SlowRate(0.3, threshold=1.0) | SlowRate(0.05, threshold=10.0)

    Args:
        ratio: Slow call rate threshold (0.0 to 1.0)
        threshold: Duration in seconds at or above which a call counts as slow
    """

    def __init__(self, ratio: float, *, threshold: float) -> None:
        if ratio <= 0 or ratio > 1:
            raise ValueError("Ratio must be between 0 and 1")
        if threshold <= 0:
            raise ValueError("Threshold must be greater than 0")
        self._ratio = ratio
        self.threshold = threshold

    def __call__(self, ctx: CallContext) -> bool:
        if ctx.metric.total_count == 0:
            return False
        slow_count = ctx.metric.slow_counts.get(self.threshold, 0)
        return slow_count / ctx.metric.total_count >= self._ratio


class FailureStreak(Tripper):
    """Tripper based on consecutive failure count.

    Returns true when the number of consecutive failures reaches the threshold.
    Useful for fast failure detection during cold start or when external service
    is completely down.

    Examples:
        >>> # Trip after 5 consecutive failures
        >>> tripper = FailureStreak(5)
        >>>
        >>> # Combine with other trippers for comprehensive protection
        >>> tripper = FailureStreak(5) | (MinRequests(20) & FailureRate(0.5))

    Args:
        count: Number of consecutive failures required to trip
    """

    def __init__(self, count: int) -> None:
        if count <= 0:
            raise ValueError("Count must be greater than zero")
        self._count = count

    def __call__(self, ctx: CallContext) -> bool:
        return ctx.consecutive_failures >= self._count
