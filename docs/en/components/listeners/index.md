# Listeners

Listeners detect circuit breaker state transitions and send notifications to external systems.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.listeners.log import LogListener
from fluxgate.listeners.prometheus import PrometheusListener

cb = CircuitBreaker(
    name="api",
    ...,
    listeners=[
        LogListener(),
        PrometheusListener(),
    ],
)
```

## Signal {#signal}

Listeners receive a `Signal` object on state transitions:

```python
from dataclasses import dataclass
from fluxgate.state import StateEnum

@dataclass(frozen=True)
class Signal:
    circuit_name: str     # Circuit breaker name
    old_state: StateEnum  # Previous state
    new_state: StateEnum  # New state
    timestamp: float      # Transition time (Unix timestamp)
```

## Sync vs Async {#sync-vs-async}

### Synchronous Listeners (IListener)

Can be used with both `CircuitBreaker` and `AsyncCircuitBreaker`:

```python
from fluxgate.interfaces import IListener
from fluxgate.signal import Signal

class CustomListener(IListener):
    def __call__(self, signal: Signal) -> None:
        print(f"{signal.circuit_name}: {signal.old_state} → {signal.new_state}")
```

> **Warning**: When using synchronous listeners with `AsyncCircuitBreaker`, avoid blocking I/O operations (network calls, file writes, etc.) as they will block the event loop. Use `IAsyncListener` for operations requiring I/O.

### Asynchronous Listeners (IAsyncListener)

Only available for `AsyncCircuitBreaker`:

<!--pytest.mark.skip-->

```python
from fluxgate.interfaces import IAsyncListener
from fluxgate.signal import Signal

class CustomAsyncListener(IAsyncListener):
    async def __call__(self, signal: Signal) -> None:
        await send_notification(signal)
```

## Available Listeners {#available-listeners}

### [LogListener](logging.md)

Logs state transitions using Python's standard `logging` module.

<!--pytest.mark.skip-->

```python
from fluxgate.listeners.log import LogListener

cb = CircuitBreaker(..., listeners=[LogListener()])
```

### [PrometheusListener](prometheus.md)

Collects Prometheus metrics for integration with monitoring systems.

```bash
pip install fluxgate[prometheus]
```

<!--pytest.mark.skip-->

```python
from fluxgate.listeners.prometheus import PrometheusListener

cb = CircuitBreaker(..., listeners=[PrometheusListener()])
```

### [SlackListener / AsyncSlackListener](slack.md)

Sends state transition notifications to Slack channels.

```bash
pip install fluxgate[slack]
```

<!--pytest.mark.skip-->

```python
from fluxgate.listeners.slack import SlackListener, AsyncSlackListener

# Sync
sync_cb = CircuitBreaker(..., listeners=[
    SlackListener(channel="C1234567890", token="xoxb-...")
])

# Async
async_cb = AsyncCircuitBreaker(..., listeners=[
    AsyncSlackListener(channel="C1234567890", token="xoxb-...")
])
```

## Custom Listeners {#custom-listeners}

### Synchronous Listener

<!--pytest.mark.skip-->

```python
from fluxgate.interfaces import IListener
from fluxgate.signal import Signal
from fluxgate.state import StateEnum

class DatabaseListener(IListener):
    def __init__(self, db_connection):
        self.db = db_connection

    def __call__(self, signal: Signal) -> None:
        if signal.new_state == StateEnum.OPEN:
            self.db.execute(
                "INSERT INTO circuit_events (name, timestamp) VALUES (?, ?)",
                (signal.circuit_name, signal.timestamp)
            )
```

### Asynchronous Listener

```python
import httpx
from fluxgate.interfaces import IAsyncListener
from fluxgate.signal import Signal

class WebhookListener(IAsyncListener):
    def __init__(self, webhook_url: str):
        self.url = webhook_url
        self.client = httpx.AsyncClient()

    async def __call__(self, signal: Signal) -> None:
        payload = {
            "circuit": signal.circuit_name,
            "transition": f"{signal.old_state.value} -> {signal.new_state.value}",
            "timestamp": signal.timestamp,
        }
        await self.client.post(self.url, json=payload)
```

## Error Handling {#error-handling}

Listener exceptions don't affect circuit breaker operation. Exceptions are automatically logged, and the circuit breaker continues normally.

## Combining Multiple Listeners {#combining-listeners}

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.listeners.log import LogListener
from fluxgate.listeners.prometheus import PrometheusListener
from fluxgate.listeners.slack import SlackListener

cb = CircuitBreaker(
    name="payment_api",
    ...,
    listeners=[
        LogListener(),
        PrometheusListener(),
        SlackListener(channel="C1234567890", token="xoxb-..."),
    ],
)
```

## Next Steps {#next-steps}

- [LogListener](logging.md) - Logging configuration
- [PrometheusListener](prometheus.md) - Prometheus integration
- [SlackListener](slack.md) - Slack notification setup
