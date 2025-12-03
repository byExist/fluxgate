import logging
import time

from fluxgate.interfaces import IListener
from fluxgate.signal import Signal
from fluxgate.state import StateEnum

__all__ = ["LogListener"]


class LogListener(IListener):
    """Listener that logs circuit breaker state transitions.

    Logs state changes using Python's standard logging module.
    Works with both CircuitBreaker and AsyncCircuitBreaker.

    Args:
        logger: Custom logger instance. If None, uses the root logger.
        level_map: Mapping from new_state to log level (logging.INFO, etc.).
            Default levels: OPEN/FORCED_OPEN -> WARNING, others -> INFO.

    Note:
        logging methods are thread-safe and can be safely used in async contexts.

    Examples:
        Basic usage with default logger:

        >>> import logging
        >>> from fluxgate import CircuitBreaker
        >>> from fluxgate.listeners.log import LogListener
        >>>
        >>> logging.basicConfig(level=logging.INFO)
        >>> cb = CircuitBreaker(..., listeners=[LogListener()])

        With custom logger:

        >>> logger = logging.getLogger("my_app.circuit_breaker")
        >>> cb = CircuitBreaker(..., listeners=[LogListener(logger=logger)])

        With custom level_map:

        >>> from fluxgate.state import StateEnum
        >>> level_map = {
        ...     StateEnum.OPEN: logging.ERROR,
        ...     StateEnum.HALF_OPEN: logging.WARNING,
        ...     StateEnum.CLOSED: logging.DEBUG,
        ... }
        >>> cb = CircuitBreaker(..., listeners=[LogListener(level_map=level_map)])
    """

    DEFAULT_LEVEL_MAP: dict[StateEnum, int] = {
        StateEnum.CLOSED: logging.INFO,
        StateEnum.OPEN: logging.WARNING,
        StateEnum.HALF_OPEN: logging.INFO,
        StateEnum.METRICS_ONLY: logging.INFO,
        StateEnum.DISABLED: logging.INFO,
        StateEnum.FORCED_OPEN: logging.WARNING,
    }

    def __init__(
        self,
        logger: logging.Logger | None = None,
        level_map: dict[StateEnum, int] | None = None,
    ) -> None:
        self._logger = logger or logging.getLogger()
        self._level_map = {**self.DEFAULT_LEVEL_MAP, **(level_map or {})}

    def __call__(self, signal: Signal) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(signal.timestamp))
        level = self._level_map.get(signal.new_state, logging.INFO)
        self._logger.log(
            level,
            "[%s] Circuit Breaker '%s' transitioned from %s to %s",
            timestamp,
            signal.circuit_name,
            signal.old_state.value,
            signal.new_state.value,
        )
