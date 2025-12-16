"""Permit strategies for controlling call admission in HALF_OPEN state."""

from random import random
from time import time

from fluxgate.interfaces import IPermit

__all__ = ["All", "Random", "RampUp"]


class All(IPermit):
    """Permit strategy that always allows calls.

    Useful for testing or when you want all calls to pass through
    in HALF_OPEN state.

    Examples:
        >>> permit = All()
    """

    def __call__(self, _changed_at: float) -> bool:
        return True


class Random(IPermit):
    """Permit strategy with random sampling in HALF_OPEN state.

    Allows calls randomly based on a fixed probability ratio.
    Simple and effective for limiting concurrent calls during recovery.

    Examples:
        >>> # Allow 50% of calls in HALF_OPEN state
        >>> permit = Random(ratio=0.5)

    Args:
        ratio: Probability of allowing a call (0.0 to 1.0)
    """

    def __init__(self, ratio: float) -> None:
        if not (0.0 <= ratio <= 1.0):
            raise ValueError("Ratio must be between 0.0 and 1.0")
        self._ratio = ratio

    def __call__(self, _changed_at: float) -> bool:
        return random() < self._ratio


class RampUp(IPermit):
    """Permit strategy that gradually increases allowed traffic over time.

    Starts with a low permit ratio and gradually increases to the final ratio
    over the specified duration. Useful for smooth recovery without sudden load spikes.

    Examples:
        >>> # Start at 10%, ramp up to 80% over 60 seconds
        >>> permit = RampUp(initial=0.1, final=0.8, duration=60.0)

    Args:
        initial: Initial permit ratio (0.0 to 1.0)
        final: Final permit ratio (0.0 to 1.0, must be >= initial)
        duration: Ramp-up duration in seconds
    """

    def __init__(self, initial: float, final: float, duration: float) -> None:
        if not (0.0 <= initial <= final <= 1.0):
            raise ValueError("Initial and final must be between 0.0 and 1.0")
        if duration <= 0:
            raise ValueError("Duration must be greater than zero")
        self._initial = initial
        self._final = final
        self._duration = duration

    def __call__(self, changed_at: float) -> bool:
        elapsed = time() - changed_at
        if elapsed >= self._duration:
            return random() < self._final
        ratio = self._initial + (self._final - self._initial) * (
            elapsed / self._duration
        )
        return random() < ratio
