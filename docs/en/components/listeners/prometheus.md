# PrometheusListener

The `PrometheusListener` exports the state and transitions of your circuit breakers as metrics that can be scraped by a Prometheus server. This allows you to build dashboards, create alerts, and gain deep insights into the stability of your services over time.

## Installation {#installation}

This listener requires the `prometheus-client` library. You can install it as an extra:

```bash
pip install fluxgate[prometheus]
```

---

## Exposed Metrics {#metrics}

The listener exports two core metrics.

### `circuit_breaker_state` (Gauge)

This metric indicates the **current state** of a circuit breaker. Since it's a gauge, it can go up or down.

**Labels:**

- `circuit_name`: The name of the circuit breaker.
- `state`: The name of the state (`closed`, `open`, `half_open`, etc.).

**Values:**

- `1`: The circuit is currently in this state.
- `0`: The circuit is not in this state.

**Example PromQL Usage:**

- **Find all open circuits:**

    ```promql
    circuit_breaker_state{state="open"} == 1
    ```

- **Count the number of circuits in each state:**

    ```promql
    sum(circuit_breaker_state) by (state)
    ```

### `circuit_breaker_state_transition_total` (Counter)

This metric **counts** the total number of times a circuit breaker has transitioned from one state to another. Since it's a counter, its value only ever increases.

**Labels:**

- `circuit_name`: The name of the circuit breaker.
- `old_state`: The state the circuit transitioned *from*.
- `new_state`: The state the circuit transitioned *to*.

**Example PromQL Usage:**

- **Calculate the rate of circuits tripping open over the last 5 minutes:**

    ```promql
    sum(rate(circuit_breaker_state_transition_total{new_state="open"}[5m])) by (circuit_name)
    ```

- **Count all transitions into the `HALF_OPEN` state in the last hour:**

    ```promql
    increase(circuit_breaker_state_transition_total{new_state="half_open"}[1h])
    ```

---

## Usage {#usage}

### Basic Setup

For simple scripts or background workers, you can start the Prometheus client's HTTP server in a separate thread.

<!--pytest.mark.skip-->

```python
from prometheus_client import start_http_server
from fluxgate import CircuitBreaker
from fluxgate.listeners.prometheus import PrometheusListener

# Start the Prometheus metrics server on port 8000.
# This runs in a background thread and does not block.
start_http_server(8000)

cb = CircuitBreaker(
    name="payment_api",
    ...,
    listeners=[PrometheusListener()],
)

# Your application logic here...

# The metrics will be available at http://localhost:8000/metrics
```

### Integration with Web Frameworks (FastAPI)

When using a web framework like FastAPI or Flask, you should integrate the Prometheus metrics endpoint directly into your application instead of starting a separate server.

<!--pytest.mark.skip-->

```python
from fastapi import FastAPI
from prometheus_client import make_asgi_app
from fluxgate import AsyncCircuitBreaker
from fluxgate.listeners.prometheus import PrometheusListener

# Create an ASGI app for the Prometheus metrics.
metrics_app = make_asgi_app()

app = FastAPI()
# Mount the metrics app at the /metrics endpoint.
app.mount("/metrics", metrics_app)

cb = AsyncCircuitBreaker(
    name="api_gateway",
    ...,
    listeners=[PrometheusListener()],
)

@app.get("/")
@cb
async def root():
    # Your protected API logic...
    return {"message": "Hello World"}
```

> **Note**: The `prometheus-client` library is thread-safe, so a single `PrometheusListener` instance can be safely used with both synchronous and asynchronous circuit breakers. See the [official documentation](https://prometheus.github.io/client_python/) for more details.

---

## Monitoring Multiple Circuit Breakers {#multiple-circuits}

To monitor multiple circuit breakers in the same application, simply reuse the same `PrometheusListener` instance. The metrics will be correctly labeled with the `circuit_name` for each breaker.

<!--pytest.mark.skip-->

```python
from prometheus_client import start_http_server
from fluxgate import CircuitBreaker
from fluxgate.listeners.prometheus import PrometheusListener

start_http_server(8000)

# Create a single listener instance.
listener = PrometheusListener()

# Add the same instance to multiple breakers.
payment_cb = CircuitBreaker(name="payment_api", ..., listeners=[listener])
inventory_cb = CircuitBreaker(name="inventory_api", ..., listeners=[listener])
```

---

## Grafana Dashboard Example

Here are some examples of how you could visualize these metrics in a Grafana dashboard.

### Panel: "Currently Open Circuits" (Stat)

- **Query**: `sum(circuit_breaker_state{state="open"})`
- **Visualization**: Stat
- **Unit**: None
- **Thresholds**: Base: 0, Step 1: 1 (Warning), Step 2: 5 (Critical)
- **Description**: Shows a real-time count of all circuit breakers that are currently in the `OPEN` state.

### Panel: "Circuit Trip Rate (5m)" (Time Series)

- **Query**: `sum(rate(circuit_breaker_state_transition_total{new_state="open"}[5m])) by (circuit_name)`
- **Visualization**: Time series
- **Unit**: Transitions per second
- **Legend**: `{{circuit_name}}`
- **Description**: Shows the per-second rate of circuits tripping open, averaged over the last 5 minutes. Useful for spotting trends and identifying problematic services.

### Panel: "Circuit State Overview" (Pie Chart)

- **Query**: `sum(circuit_breaker_state) by (state)`
- **Visualization**: Pie Chart
- **Unit**: None
- **Value Options**: `All values`
- **Description**: Provides a high-level overview of the distribution of circuit breaker states across the entire system.

---

## Custom Metrics {#custom-metrics}

If you need to export additional custom metrics, you can create your own listener by implementing the `IListener` interface.

<!--pytest.mark.skip-->

```python
from prometheus_client import Counter
from fluxgate.interfaces import IListener
from fluxgate.signal import Signal
from fluxgate.state import StateEnum

# Define a custom metric to count only OPEN transitions.
OPEN_TRANSITIONS = Counter(
    'circuit_breaker_open_total',
    'Total number of times a circuit breaker has opened',
    ['circuit_name']
)

class CustomPrometheusListener(IListener):
    def __call__(self, signal: Signal) -> None:
        if signal.new_state == StateEnum.OPEN:
            OPEN_TRANSITIONS.labels(circuit_name=signal.circuit_name).inc()
```

## Next Steps {#next-steps}

- [SlackListener](slack.md): Get real-time notifications for state changes.
- [LogListener](logging.md): Configure detailed logging for transitions.
- [Listeners Overview](index.md): Return to the main listeners page.
