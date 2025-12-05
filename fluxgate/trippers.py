"""Tripper conditions for determining when to open/close the circuit."""

from __future__ import annotations

from fluxgate.interfaces import ITripper
from fluxgate.metric import Metric
from fluxgate.state import StateEnum

__all__ = [
    "Closed",
    "HalfOpened",
    "MinRequests",
    "FailureRate",
    "AvgLatency",
    "SlowRate",
    "FailureStreak",
]


class _And:
    def __init__(self, lhs: ITripper, rhs: ITripper) -> None:
        self._lhs, self._rhs = lhs, rhs

    def __call__(
        self, metric: Metric, state: StateEnum, consecutive_failures: int
    ) -> bool:
        return self._lhs(metric, state, consecutive_failures) and self._rhs(
            metric, state, consecutive_failures
        )

    def __and__(self, other: ITripper) -> ITripper:
        return _And(self, other)

    def __or__(self, other: ITripper) -> ITripper:
        return _Or(self, other)


class _Or:
    def __init__(self, lhs: ITripper, rhs: ITripper) -> None:
        self._lhs, self._rhs = lhs, rhs

    def __call__(
        self, metric: Metric, state: StateEnum, consecutive_failures: int
    ) -> bool:
        return self._lhs(metric, state, consecutive_failures) or self._rhs(
            metric, state, consecutive_failures
        )

    def __and__(self, other: ITripper) -> ITripper:
        return _And(self, other)

    def __or__(self, other: ITripper) -> ITripper:
        return _Or(self, other)


class TripperBase(ITripper):
    """Base class for tripper conditions."""

    def __and__(self, other: ITripper) -> ITripper:
        return _And(self, other)

    def __or__(self, other: ITripper) -> ITripper:
        return _Or(self, other)


class Closed(TripperBase):
    """Tripper that returns true only when circuit is in CLOSED state.

    Used to compose conditions that should only apply when circuit is closed.

    Examples:
        >>> # Only check failure rate when circuit is closed
        >>> tripper = Closed() & FailureRate(0.5)
    """

    def __call__(
        self, _metric: Metric, state: StateEnum, _consecutive_failures: int
    ) -> bool:
        return state == StateEnum.CLOSED


class HalfOpened(TripperBase):
    """Tripper that returns true only when circuit is in HALF_OPEN state.

    Used to compose conditions that should only apply when circuit is half-open.

    Examples:
        >>> # Only check failure rate when circuit is half-open
        >>> tripper = HalfOpened() & FailureRate(0.3)
    """

    def __call__(
        self, _metric: Metric, state: StateEnum, _consecutive_failures: int
    ) -> bool:
        return state == StateEnum.HALF_OPEN


class MinRequests(TripperBase):
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

    def __call__(
        self, metric: Metric, _state: StateEnum, _consecutive_failures: int
    ) -> bool:
        return metric.total_count >= self._count


class FailureRate(TripperBase):
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

    def __call__(
        self, metric: Metric, _state: StateEnum, _consecutive_failures: int
    ) -> bool:
        if metric.total_count == 0:
            return False
        failure_rate = metric.failure_count / metric.total_count
        return failure_rate >= self._ratio


class AvgLatency(TripperBase):
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

    def __call__(
        self, metric: Metric, _state: StateEnum, _consecutive_failures: int
    ) -> bool:
        if metric.total_count == 0:
            return False
        avg_duration = metric.total_duration / metric.total_count
        return avg_duration >= self._threshold


class SlowRate(TripperBase):
    """Tripper based on slow call rate threshold.

    Returns true when the ratio of slow calls exceeds the threshold.
    Slow calls are determined by the circuit breaker's slow_threshold.

    Examples:
        >>> # Trip when 30% or more calls are slow
        >>> tripper = SlowRate(0.3)

    Args:
        ratio: Slow call rate threshold (0.0 to 1.0)
    """

    def __init__(self, ratio: float) -> None:
        if ratio <= 0 or ratio > 1:
            raise ValueError("Ratio must be between 0 and 1")
        self._ratio = ratio

    def __call__(
        self, metric: Metric, _state: StateEnum, _consecutive_failures: int
    ) -> bool:
        if metric.total_count == 0:
            return False
        slow_rate = metric.slow_count / metric.total_count
        return slow_rate >= self._ratio


class FailureStreak(TripperBase):
    """Tripper based on consecutive failure count.

    Returns true when the number of consecutive failures reaches the threshold.
    Useful for fast failure detection during cold start or when external service
    is completely down.

    Examples:
        >>> # Trip after 5 consecutive failures
        >>> tripper = ConsecutiveFailures(5)
        >>>
        >>> # Combine with other trippers for comprehensive protection
        >>> tripper = ConsecutiveFailures(5) | (MinRequests(20) & FailureRate(0.5))

    Args:
        count: Number of consecutive failures required to trip
    """

    def __init__(self, count: int) -> None:
        if count <= 0:
            raise ValueError("Count must be greater than zero")
        self._count = count

    def __call__(
        self, _metric: Metric, _state: StateEnum, consecutive_failures: int
    ) -> bool:
        return consecutive_failures >= self._count
