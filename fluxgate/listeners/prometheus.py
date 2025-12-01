from fluxgate.interfaces import IListener
from fluxgate.signal import Signal
from fluxgate.state import StateEnum
from prometheus_client import Counter, Gauge

__all__ = ["PrometheusListener"]

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


class PrometheusListener(IListener):
    """Listener that exports circuit breaker metrics to Prometheus.

    Exports two metrics:

    - circuit_breaker_state: Gauge showing current state (0 or 1 for each state)
    - circuit_breaker_state_transition: Counter of state transitions

    Works with both CircuitBreaker and AsyncCircuitBreaker.

    Note:
        prometheus_client is thread-safe and can be safely used in async contexts.

    Examples:
        >>> from prometheus_client import start_http_server
        >>> from fluxgate import CircuitBreaker, AsyncCircuitBreaker
        >>> from fluxgate.listeners.prometheus import PrometheusListener
        >>>
        >>> start_http_server(8000)
        >>>
        >>> cb = CircuitBreaker(..., listeners=[PrometheusListener()])
        >>> async_cb = AsyncCircuitBreaker(..., listeners=[PrometheusListener()])
        >>>
        >>> # Metrics available at http://localhost:8000/metrics
    """

    def __call__(self, signal: Signal) -> None:
        for state in StateEnum:
            _STATE_GAUGE.labels(
                circuit_name=signal.circuit_name,
                state=state.value,
            ).set(1 if state == signal.new_state else 0)
        _STATE_TRANSITION.labels(
            circuit_name=signal.circuit_name,
            old_state=signal.old_state.value,
            new_state=signal.new_state.value,
        ).inc()
