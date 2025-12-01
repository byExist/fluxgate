# PrometheusListener

A listener that exports circuit breaker metrics to Prometheus for monitoring.

## Installation {#installation}

```bash
pip install fluxgate[prometheus]
```

## Metrics {#metrics}

### circuit_breaker_state (Gauge)

Indicates the current state of the circuit breaker.

**Labels:**

- `circuit_name`: Circuit breaker name
- `state`: State value (`closed`, `open`, `half_open`, `metrics_only`, `disabled`, `forced_open`)

**Values:** `1` (current state) / `0` (not current state)

### circuit_breaker_state_transition (Counter)

Counts the number of state transitions.

**Labels:**

- `circuit_name`: Circuit breaker name
- `old_state`: Previous state
- `new_state`: New state

## Usage {#usage}

### Synchronous Circuit Breaker

```python
from prometheus_client import start_http_server
from fluxgate import CircuitBreaker
from fluxgate.listeners.prometheus import PrometheusListener

# Start Prometheus metrics server
start_http_server(8000)

cb = CircuitBreaker(
    name="payment_api",
    ...,
    listeners=[PrometheusListener()],
)

# Metrics: http://localhost:8000/metrics
```

### Asynchronous Circuit Breaker

```python
from prometheus_client import start_http_server
from fluxgate import AsyncCircuitBreaker
from fluxgate.listeners.prometheus import PrometheusListener

# Start Prometheus metrics server (separate thread)
start_http_server(8000)

cb = AsyncCircuitBreaker(
    name="async_api",
    ...,
    listeners=[PrometheusListener()],
)
```

### FastAPI Integration

```python
from fastapi import FastAPI
from prometheus_client import make_asgi_app
from fluxgate import AsyncCircuitBreaker
from fluxgate.listeners.prometheus import PrometheusListener

app = FastAPI()

# Mount Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

cb = AsyncCircuitBreaker(
    name="api_gateway",
    ...,
    listeners=[PrometheusListener()],
)
```

> **Note**: `prometheus_client` is thread-safe and can be used in both sync and async code.
> See the [official documentation](https://prometheus.github.io/client_python/) for details.

## Monitoring Multiple Circuit Breakers {#multiple-circuits}

```python
from prometheus_client import start_http_server
from fluxgate import CircuitBreaker
from fluxgate.listeners.prometheus import PrometheusListener

start_http_server(8000)

# Reuse listener instance
listener = PrometheusListener()

payment_cb = CircuitBreaker(name="payment_api", ..., listeners=[listener])
inventory_cb = CircuitBreaker(name="inventory_api", ..., listeners=[listener])
```

## Custom Metrics {#custom-metrics}

For additional metrics, implement `IListener` to create a custom listener:

```python
from prometheus_client import Counter
from fluxgate.interfaces import IListener
from fluxgate.signal import Signal

CUSTOM_METRIC = Counter('my_custom_metric', 'Description', ['circuit_name'])

class CustomListener(IListener):
    def __call__(self, signal: Signal) -> None:
        # Custom logic
        CUSTOM_METRIC.labels(circuit_name=signal.circuit_name).inc()
```

## Next Steps {#next-steps}

- [SlackListener](slack.md) - Real-time notification setup
- [LogListener](logging.md) - Logging configuration
- [Overview](index.md) - Back to listeners overview
