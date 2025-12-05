"""Exception trackers for determining which exceptions to count as failures."""

from typing import Callable

from fluxgate.interfaces import ITracker

__all__ = ["All", "TypeOf", "Custom"]


class _And(ITracker):
    def __init__(self, left: ITracker, right: ITracker) -> None:
        self._lhs = left
        self._rhs = right

    def __call__(self, exception: Exception) -> bool:
        return self._lhs(exception) and self._rhs(exception)

    def __and__(self, other: ITracker) -> ITracker:
        return _And(self, other)

    def __or__(self, other: ITracker) -> ITracker:
        return _Or(self, other)

    def __invert__(self) -> ITracker:
        return _Not(self)


class _Or(ITracker):
    def __init__(self, left: ITracker, right: ITracker) -> None:
        self._lhs = left
        self._rhs = right

    def __call__(self, exception: Exception) -> bool:
        return self._lhs(exception) or self._rhs(exception)

    def __and__(self, other: ITracker) -> ITracker:
        return _And(self, other)

    def __or__(self, other: ITracker) -> ITracker:
        return _Or(self, other)

    def __invert__(self) -> ITracker:
        return _Not(self)


class _Not(ITracker):
    def __init__(self, predicate: ITracker) -> None:
        self._predicate = predicate

    def __call__(self, exception: Exception) -> bool:
        return not self._predicate(exception)

    def __and__(self, other: ITracker) -> ITracker:
        return _And(self, other)

    def __or__(self, other: ITracker) -> ITracker:
        return _Or(self, other)

    def __invert__(self) -> ITracker:
        return self._predicate


class TrackerBase(ITracker):
    """Base class for exception trackers."""

    def __and__(self, other: ITracker) -> ITracker:
        return _And(self, other)

    def __or__(self, other: ITracker) -> ITracker:
        return _Or(self, other)

    def __invert__(self) -> ITracker:
        return _Not(self)


class All(TrackerBase):
    """Tracker that matches all exceptions.

    Always returns true for any exception, tracking all failures.

    Examples:
        >>> # Track all exceptions
        >>> tracker = All()
        >>>
        >>> # Track all except ValueError
        >>> tracker = All() & ~TypeOf(ValueError)

    Note:
        This is the default behavior when you want to track all exceptions.
    """

    def __call__(self, _exception: Exception) -> bool:
        return True


class TypeOf(TrackerBase):
    """Tracker that matches exceptions by type.

    Returns true if the exception is an instance of any of the specified types.

    Examples:
        >>> # Track connection and timeout errors
        >>> tracker = TypeOf(ConnectionError, TimeoutError)
        >>>
        >>> # Combine with OR
        >>> tracker = TypeOf(ValueError) | TypeOf(TypeError)

    Args:
        *types: Exception types to track as failures

    Raises:
        ValueError: If no exception types are provided
    """

    def __init__(self, *types: type[Exception]) -> None:
        if not types:
            raise ValueError("At least one exception type is required")
        self._types = types

    def __call__(self, exception: Exception) -> bool:
        return isinstance(exception, self._types)


class Custom(TrackerBase):
    """Tracker with custom exception matching logic.

    Allows arbitrary logic to determine if an exception should be tracked.

    Examples:
        >>> # Track only 503 errors from httpx
        >>> def is_503(e):
        ...     return isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 503
        >>>
        >>> tracker = Custom(is_503)

    Args:
        func: Function that takes an exception and returns bool
    """

    def __init__(self, func: Callable[[Exception], bool]) -> None:
        self._func = func

    def __call__(self, exception: Exception) -> bool:
        return self._func(exception)
