"""Fluxgate: Circuit breaker library for Python.

Examples:
    >>> from fluxgate import CircuitBreaker
    >>> from fluxgate.trippers import MinRequests, FailureRate, SlowRate
    >>>
    >>> cb = CircuitBreaker(
    ...     name="api",
    ...     tripper=MinRequests(10) & (FailureRate(0.5) | SlowRate(0.3, threshold=1.0)),
    ... )
"""

from fluxgate.circuitbreaker import CircuitBreaker, AsyncCircuitBreaker
from fluxgate.errors import CallNotPermittedError
from fluxgate.state import State

__all__ = [
    "CircuitBreaker",
    "AsyncCircuitBreaker",
    "State",
    "CallNotPermittedError",
]
