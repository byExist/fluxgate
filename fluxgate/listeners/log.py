import logging
import time

from fluxgate.listeners import Listener
from fluxgate.signal import Signal
from fluxgate.state import State

__all__ = ["LogListener"]


class LogListener(Listener):
    """Listener that logs circuit breaker state transitions.

    Logs state changes using Python's standard logging module.
    Works with both CircuitBreaker and AsyncCircuitBreaker.

    Args:
        name: Identifier for the circuit, included in every log line.
        logger: Custom logger instance. If None, uses
            ``logging.getLogger("fluxgate.listeners.log")`` so
            ``logging.getLogger("fluxgate").setLevel(...)`` scopes correctly.
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
        >>> cb = CircuitBreaker(listeners=[LogListener(name="api")])

        With custom logger:

        >>> logger = logging.getLogger("my_app.circuit_breaker")
        >>> cb = CircuitBreaker(
        ...     listeners=[LogListener(name="api", logger=logger)]
        ... )

        With custom level_map:

        >>> level_map = {
        ...     "open": logging.ERROR,
        ...     "half_open": logging.WARNING,
        ...     "closed": logging.DEBUG,
        ... }
        >>> cb = CircuitBreaker(
        ...     listeners=[LogListener(name="api", level_map=level_map)]
        ... )
    """

    DEFAULT_LEVEL_MAP: dict[State, int] = {
        "closed": logging.INFO,
        "open": logging.WARNING,
        "half_open": logging.INFO,
        "metrics_only": logging.INFO,
        "disabled": logging.INFO,
        "forced_open": logging.WARNING,
    }

    def __init__(
        self,
        name: str,
        logger: logging.Logger | None = None,
        level_map: dict[State, int] | None = None,
    ) -> None:
        self._name = name
        self._logger = logger or logging.getLogger(__name__)
        self._level_map = {**self.DEFAULT_LEVEL_MAP, **(level_map or {})}

    def __call__(self, signal: Signal) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(signal.timestamp))
        level = self._level_map.get(signal.new_state, logging.INFO)
        self._logger.log(
            level,
            "[%s] Circuit Breaker '%s' transitioned from %s to %s",
            timestamp,
            self._name,
            signal.old_state,
            signal.new_state,
        )
