import logging
import time

from fluxgate.interfaces import IListener
from fluxgate.signal import Signal

__all__ = ["LogListener"]


class LogListener(IListener):
    """Listener that logs circuit breaker state transitions.

    Logs state changes at INFO level using Python's standard logging module.
    Works with both CircuitBreaker and AsyncCircuitBreaker.

    Note:
        logging.info is thread-safe and can be safely used in async contexts.

    Examples:
        >>> import logging
        >>> from fluxgate import CircuitBreaker, AsyncCircuitBreaker
        >>> from fluxgate.listeners.log import LogListener
        >>>
        >>> logging.basicConfig(level=logging.INFO)
        >>>
        >>> cb = CircuitBreaker(..., listeners=[LogListener()])
        >>> async_cb = AsyncCircuitBreaker(..., listeners=[LogListener()])
        >>>
        >>> # Logs: [2025-01-15 10:30:45] Circuit Breaker 'api' transitioned from CLOSED to OPEN
    """

    def __call__(self, signal: Signal) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(signal.timestamp))
        logging.info(
            f"[{timestamp}] Circuit Breaker '{signal.circuit_name}' "
            f"transitioned from {signal.old_state.value} to {signal.new_state.value}"
        )
