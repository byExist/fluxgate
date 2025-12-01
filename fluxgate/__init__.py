"""Fluxgate: Circuit breaker library for Python.

Examples:
    >>> from fluxgate import CircuitBreaker
    >>> from fluxgate.windows import CountWindow
    >>> from fluxgate.trackers import TypeOf
    >>> from fluxgate.trippers import Closed, MinRequests, FailureRate
    >>> from fluxgate.retries import Cooldown
    >>> from fluxgate.permits import Random
    >>> from fluxgate.listeners.log import LogListener
    >>>
    >>> cb = CircuitBreaker(
    ...     name="api",
    ...     window=CountWindow(100),
    ...     tracker=TypeOf(ConnectionError),
    ...     tripper=Closed() & MinRequests(10) & FailureRate(0.5),
    ...     retry=Cooldown(60.0),
    ...     permit=Random(0.5),
    ...     listeners=[LogListener()],
    ...     slow_threshold=1.0,
    ... )
"""

from fluxgate.circuitbreaker import CircuitBreaker, AsyncCircuitBreaker
from fluxgate.errors import CallNotPermittedError
from fluxgate.state import StateEnum

__all__ = [
    "CircuitBreaker",
    "AsyncCircuitBreaker",
    "StateEnum",
    "CallNotPermittedError",
]
