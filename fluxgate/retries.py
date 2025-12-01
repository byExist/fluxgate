"""Retry strategies for transitioning from OPEN to HALF_OPEN state."""

import time
from random import uniform

from fluxgate.interfaces import IRetry

__all__ = ["Always", "Never", "Cooldown", "Backoff"]


class RetryBase(IRetry):
    """Base class for retry strategies."""

    pass


class Always(RetryBase):
    """Retry strategy that always allows transition to HALF_OPEN.

    Circuit immediately attempts to recover on every call.

    Examples:
        >>> retry = Always()  # Always try to recover
    """

    def __call__(self, _changed_at: float, _reopens: int) -> bool:
        return True


class Never(RetryBase):
    """Retry strategy that never allows transition to HALF_OPEN.

    Circuit stays OPEN indefinitely until manually reset.

    Examples:
        >>> retry = Never()  # Require manual intervention
    """

    def __call__(self, _changed_at: float, _reopens: int) -> bool:
        return False


class Cooldown(RetryBase):
    """Retry strategy with fixed cooldown period.

    Allows transition to HALF_OPEN after a fixed duration has elapsed.
    Optional jitter can be added to avoid thundering herd.

    Examples:
        >>> # Wait 60 seconds before retry
        >>> retry = Cooldown(duration=60.0)
        >>>
        >>> # Wait 60 seconds with ±10% jitter
        >>> retry = Cooldown(duration=60.0, jitter_ratio=0.1)

    Args:
        duration: Cooldown duration in seconds
        jitter_ratio: Random jitter ratio (0.0 to 1.0, default 0.0)
    """

    def __init__(self, duration: float, jitter_ratio: float = 0.0) -> None:
        if duration <= 0:
            raise ValueError("Duration must be greater than zero")
        if not (0.0 <= jitter_ratio < 1.0):
            raise ValueError("Jitter ratio must be between 0.0 and 1.0")
        self._duration = duration
        self._jitter_ratio = jitter_ratio

    def __call__(self, changed_at: float, _reopens: int) -> bool:
        if self._jitter_ratio > 0:
            jitter = uniform(-self._jitter_ratio, self._jitter_ratio)
            actual_duration = self._duration * (1 + jitter)
        else:
            actual_duration = self._duration
        elapsed = time.time() - changed_at
        return elapsed >= actual_duration


class Backoff(RetryBase):
    """Retry strategy with exponential backoff.

    Wait time increases exponentially with each reopen: initial * (multiplier ^ reopens).
    Useful for giving the service more time to recover after repeated failures.

    Examples:
        >>> # Start with 10s, double each time, max 300s
        >>> retry = Backoff(initial=10.0, multiplier=2.0, max_duration=300.0)
        >>> # Reopens: 0->10s, 1->20s, 2->40s, 3->80s, 4->160s, 5+->300s
        >>>
        >>> # With jitter to avoid thundering herd
        >>> retry = Backoff(initial=10.0, multiplier=2.0, jitter_ratio=0.1)

    Args:
        initial: Initial wait duration in seconds
        multiplier: Backoff multiplier (must be > 1.0)
        max_duration: Maximum wait duration in seconds
        jitter_ratio: Random jitter ratio (0.0 to 1.0, default 0.0)
    """

    def __init__(
        self,
        initial: float,
        multiplier: float = 2.0,
        max_duration: float = 300.0,
        jitter_ratio: float = 0.0,
    ) -> None:
        if initial <= 0:
            raise ValueError("Initial duration must be greater than zero")
        if multiplier <= 1.0:
            raise ValueError("Multiplier must be greater than 1.0")
        if max_duration < initial:
            raise ValueError("Max duration must be >= initial duration")
        if not (0.0 <= jitter_ratio < 1.0):
            raise ValueError("Jitter ratio must be between 0.0 and 1.0")

        self._initial = initial
        self._multiplier = multiplier
        self._max = max_duration
        self._jitter_ratio = jitter_ratio

    def __call__(self, changed_at: float, reopens: int) -> bool:
        # Calculate wait duration based on reopens count
        duration = min(self._initial * (self._multiplier**reopens), self._max)

        if self._jitter_ratio > 0:
            jitter = uniform(-self._jitter_ratio, self._jitter_ratio)
            actual_duration = duration * (1 + jitter)
        else:
            actual_duration = duration

        elapsed = time.time() - changed_at
        return elapsed >= actual_duration
