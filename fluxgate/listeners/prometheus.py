from typing import get_args

from fluxgate.listeners import Listener
from fluxgate.signal import Signal
from fluxgate.state import State
from prometheus_client import CollectorRegistry, Counter, Gauge

__all__ = ["PrometheusListener"]

_ALL_STATES: tuple[State, ...] = get_args(State)

_STATE_GAUGE = Gauge(
    name="circuit_breaker_state",
    documentation="Current state of the circuit breaker",
    labelnames=["circuit_name", "state"],
)
_STATE_TRANSITION = Counter(
    name="circuit_breaker_state_transition",
    documentation="Count of state transitions for circuit breakers",
    labelnames=["circuit_name", "old_state", "new_state"],
)
_STATE_GAUGE.clear()
_STATE_TRANSITION.clear()


class PrometheusListener(Listener):
    """Listener that exports circuit breaker metrics to Prometheus.

    Exports two metrics:

    - circuit_breaker_state: Gauge showing current state (0 or 1 for each state)
    - circuit_breaker_state_transition: Counter of state transitions

    Works with both CircuitBreaker and AsyncCircuitBreaker.

    Args:
        name: Identifier used as the ``circuit_name`` label on emitted metrics.
        registry: Optional ``CollectorRegistry`` to register metrics into.
            ``None`` (default) writes to the module-level metrics on the
            default ``prometheus_client.REGISTRY``. Pass a dedicated registry
            to isolate fluxgate's metrics under ``importlib.reload`` /
            ``uvicorn --reload``, or when another component already exports a
            metric named ``circuit_breaker_state``.

    Note:
        prometheus_client is thread-safe and can be safely used in async contexts.

    Examples:
        >>> from prometheus_client import start_http_server
        >>> from fluxgate import CircuitBreaker, AsyncCircuitBreaker
        >>> from fluxgate.listeners.prometheus import PrometheusListener
        >>>
        >>> start_http_server(8000)
        >>>
        >>> cb = CircuitBreaker(listeners=[PrometheusListener(name="api")])
        >>> async_cb = AsyncCircuitBreaker(
        ...     listeners=[PrometheusListener(name="api")]
        ... )
        >>>
        >>> # Metrics available at http://localhost:8000/metrics
    """

    def __init__(
        self,
        name: str,
        registry: CollectorRegistry | None = None,
    ) -> None:
        self._name = name
        if registry is None:
            self._gauge = _STATE_GAUGE
            self._counter = _STATE_TRANSITION
        else:
            self._gauge = Gauge(
                name="circuit_breaker_state",
                documentation="Current state of the circuit breaker",
                labelnames=["circuit_name", "state"],
                registry=registry,
            )
            self._counter = Counter(
                name="circuit_breaker_state_transition",
                documentation="Count of state transitions for circuit breakers",
                labelnames=["circuit_name", "old_state", "new_state"],
                registry=registry,
            )

    def __call__(self, signal: Signal) -> None:
        for state in _ALL_STATES:
            self._gauge.labels(
                circuit_name=self._name,
                state=state,
            ).set(1 if state == signal.new_state else 0)
        self._counter.labels(
            circuit_name=self._name,
            old_state=signal.old_state,
            new_state=signal.new_state,
        ).inc()

    def close(self) -> None:
        """Drop every labelset this listener registered. Idempotent."""
        for state in _ALL_STATES:
            self._gauge.remove(self._name, state)
        for old_state in _ALL_STATES:
            for new_state in _ALL_STATES:
                self._counter.remove(self._name, old_state, new_state)
