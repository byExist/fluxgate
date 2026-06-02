"""Listener protocols for circuit breaker state transitions."""

from typing import Protocol, runtime_checkable

from fluxgate.signal import Signal

__all__ = ["Listener", "AsyncListener"]


@runtime_checkable
class Listener(Protocol):
    """Protocol for synchronous circuit breaker listeners.

    Any callable with the matching signature satisfies this protocol —
    a plain function or a class implementing ``__call__``.
    """

    def __call__(self, signal: Signal, /) -> None: ...


@runtime_checkable
class AsyncListener(Protocol):
    """Protocol for asynchronous circuit breaker listeners."""

    async def __call__(self, signal: Signal, /) -> None: ...
