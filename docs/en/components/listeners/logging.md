# LogListener

The `LogListener` provides the simplest way to observe your circuit breaker's behavior. It hooks into Python's standard `logging` module to record state transitions, giving you a clear, chronological view of how the breaker is operating.

It works identically for both `CircuitBreaker` and `AsyncCircuitBreaker`.

## Basic Usage {#usage}

Simply add `LogListener` to the `listeners` list of your circuit breaker.

<!--pytest.mark.skip-->

```python
import logging
from fluxgate import CircuitBreaker
from fluxgate.listeners.log import LogListener

# Basic configuration for console logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

cb = CircuitBreaker(
    name="payment_api",
    ...,
    listeners=[LogListener()],
)
```

When the circuit breaker changes state, it will produce a log record like this:

```text
[2025-01-15 10:30:45] Circuit Breaker 'payment_api' transitioned from CLOSED to OPEN
[2025-01-15 10:31:45] Circuit Breaker 'payment_api' transitioned from OPEN to HALF_OPEN
[2025-01-15 10:31:50] Circuit Breaker 'payment_api' transitioned from HALF_OPEN to CLOSED
```

---

## Custom Logger {#custom-logger}

By default, `LogListener` uses the root logger. You can inject your own logger for better control over log routing and formatting.

<!--pytest.mark.skip-->

```python
import logging
from fluxgate import CircuitBreaker
from fluxgate.listeners.log import LogListener

# Create a dedicated logger for circuit breaker events
cb_logger = logging.getLogger("myapp.circuit_breaker")
cb_logger.setLevel(logging.INFO)

cb = CircuitBreaker(
    name="payment_api",
    ...,
    listeners=[LogListener(logger=cb_logger)],
)
```

---

## Custom Log Levels {#custom-log-levels}

Use `level_map` to customize the log level for each state transition. By default, transitions to `OPEN` and `FORCED_OPEN` are logged at `WARNING` level, while others are logged at `INFO`.

<!--pytest.mark.skip-->

```python
import logging
from fluxgate import CircuitBreaker
from fluxgate.listeners.log import LogListener
from fluxgate.state import StateEnum

# Log OPEN transitions as ERROR for alerting
level_map = {
    StateEnum.OPEN: logging.ERROR,
    StateEnum.HALF_OPEN: logging.WARNING,
    StateEnum.CLOSED: logging.DEBUG,
}

cb = CircuitBreaker(
    name="payment_api",
    ...,
    listeners=[LogListener(level_map=level_map)],
)
```

You can also combine both options:

<!--pytest.mark.skip-->

```python
cb_logger = logging.getLogger("myapp.circuit_breaker")
listener = LogListener(logger=cb_logger, level_map=level_map)
```

---

## Implementing Structured (JSON) Logging {#structured-logging}

For better observability in modern platforms, you can create a custom listener to output logs in a structured format like JSON.

```python
import json
import logging
from fluxgate.interfaces import IListener
from fluxgate.signal import Signal

class JsonLogListener(IListener):
    def __init__(self, logger):
        self.logger = logger

    def __call__(self, signal: Signal) -> None:
        log_data = {
            "message": "Circuit breaker transition",
            "circuit_name": signal.circuit_name,
            "previous_state": signal.old_state.value,
            "current_state": signal.new_state.value,
            "timestamp_utc": signal.timestamp,
        }
        self.logger.info(json.dumps(log_data))

# Usage
json_logger = logging.getLogger("json_logger")
cb_listener = JsonLogListener(json_logger)
```

## Configuring File Logging {#file-logging}

To send circuit breaker logs to a file, configure a suitable handler in your application's logging setup. `LogListener` will automatically use this configuration.

<!--pytest.mark.skip-->

```python
import logging
from logging.handlers import RotatingFileHandler
from fluxgate import CircuitBreaker
from fluxgate.listeners.log import LogListener

# Configure a rotating file handler
handler = RotatingFileHandler(
    filename='circuit_breaker.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
)
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

# Add the handler to the root logger
root_logger = logging.getLogger()
root_logger.addHandler(handler)
root_logger.setLevel(logging.INFO)

# LogListener will now write to the file via the root logger.
log_listener = LogListener()
```

## Next Steps {#next-steps}

- [PrometheusListener](prometheus.md): Expose metrics for time-series monitoring.
- [SlackListener](slack.md): Send real-time notifications on state changes.
- [Listeners Overview](index.md): Return to the main listeners page.
