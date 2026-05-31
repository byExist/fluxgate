# Listeners

Listeners detect circuit breaker state transitions and send notifications to external systems. Each listener carries its own `name` — used as a label in metrics, in log lines, or as the identifier shown in alerts.

```python
from fluxgate import CircuitBreaker
from fluxgate.listeners.log import LogListener
from fluxgate.listeners.prometheus import PrometheusListener

cb = CircuitBreaker(
    ...,
    listeners=[
        LogListener(name="payment_api"),
        PrometheusListener(name="payment_api"),
    ],
)
```

## Signal {#signal}

Listeners receive a `Signal` object on state transitions:

```python
from dataclasses import dataclass
from fluxgate.state import State

@dataclass(frozen=True)
class Signal:
    old_state: State  # Previous state
    new_state: State  # New state
    timestamp: float      # Transition time (Unix timestamp)
```

## Sync vs Async {#sync-vs-async}

### Synchronous Listeners (Listener)

Can be used with both `CircuitBreaker` and `AsyncCircuitBreaker`:

```python
from fluxgate.listeners import Listener
from fluxgate.signal import Signal

class CustomListener(Listener):
    def __init__(self, name: str) -> None:
        self._name = name

    def __call__(self, signal: Signal) -> None:
        print(f"{self._name}: {signal.old_state} → {signal.new_state}")
```

> **Warning**: When using synchronous listeners with `AsyncCircuitBreaker`, avoid blocking I/O operations (network calls, file writes, etc.) as they will block the event loop. Use `AsyncListener` for operations requiring I/O.

### Asynchronous Listeners (AsyncListener)

Only available for `AsyncCircuitBreaker`:

```python
from fluxgate.listeners import AsyncListener
from fluxgate.signal import Signal

class CustomAsyncListener(AsyncListener):
    async def __call__(self, signal: Signal) -> None:
        await send_notification(signal)
```

## Available Listeners {#available-listeners}

### [LogListener](logging.md)

Logs state transitions using Python's standard `logging` module.

```python
from fluxgate.listeners.log import LogListener

cb = CircuitBreaker(..., listeners=[LogListener(name="payment_api")])
```

### [PrometheusListener](prometheus.md)

Collects Prometheus metrics for integration with monitoring systems.

```bash
pip install fluxgate[prometheus]
```

```python
from fluxgate.listeners.prometheus import PrometheusListener

cb = CircuitBreaker(..., listeners=[PrometheusListener(name="payment_api")])
```

### [SlackListener / AsyncSlackListener](slack.md)

Sends state transition notifications to Slack channels.

```bash
pip install fluxgate[slack]
```

```python
from fluxgate.listeners.slack import SlackListener, AsyncSlackListener

# Sync
sync_cb = CircuitBreaker(..., listeners=[
    SlackListener(name="payment_api", channel="C1234567890", token="xoxb-...")
])

# Async
async_cb = AsyncCircuitBreaker(..., listeners=[
    AsyncSlackListener(name="payment_api", channel="C1234567890", token="xoxb-...")
])
```

## Custom Listeners {#custom-listeners}

### Synchronous Listener

```python
from fluxgate.listeners import Listener
from fluxgate.signal import Signal
from fluxgate.state import State

class DatabaseListener(Listener):
    def __init__(self, name: str, db_connection):
        self._name = name
        self.db = db_connection

    def __call__(self, signal: Signal) -> None:
        if signal.new_state == "open":
            self.db.execute(
                "INSERT INTO circuit_events (name, timestamp) VALUES (?, ?)",
                (self._name, signal.timestamp)
            )
```

### Asynchronous Listener

```python
import httpx
from fluxgate.listeners import AsyncListener
from fluxgate.signal import Signal

class WebhookListener(AsyncListener):
    def __init__(self, name: str, webhook_url: str):
        self._name = name
        self.url = webhook_url
        self.client = httpx.AsyncClient()

    async def __call__(self, signal: Signal) -> None:
        payload = {
            "circuit": self._name,
            "transition": f"{signal.old_state.value} -> {signal.new_state.value}",
            "timestamp": signal.timestamp,
        }
        await self.client.post(self.url, json=payload)
```

## Error Handling {#error-handling}

Listener exceptions don't affect circuit breaker operation. Exceptions are automatically logged, and the circuit breaker continues normally.

## Combining Multiple Listeners {#combining-listeners}

```python
from fluxgate import CircuitBreaker
from fluxgate.listeners.log import LogListener
from fluxgate.listeners.prometheus import PrometheusListener
from fluxgate.listeners.slack import SlackListener

cb = CircuitBreaker(
    ...,
    listeners=[
        LogListener(name="payment_api"),
        PrometheusListener(name="payment_api"),
        SlackListener(name="payment_api", channel="C1234567890", token="xoxb-..."),
    ],
)
```

## Next Steps {#next-steps}

- [LogListener](logging.md) - Logging configuration
- [PrometheusListener](prometheus.md) - Prometheus integration
- [SlackListener](slack.md) - Slack notification setup
