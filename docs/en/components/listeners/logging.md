# LogListener

A listener that logs circuit breaker state transitions using Python's standard `logging` module.

## Usage {#usage}

### Synchronous Circuit Breaker

```python
import logging
from fluxgate import CircuitBreaker
from fluxgate.listeners.log import LogListener

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

cb = CircuitBreaker(
    name="payment_api",
    ...,
    listeners=[LogListener()],
)
```

**Output Example:**

```
[2025-01-15 10:30:45] Circuit Breaker 'payment_api' transitioned from CLOSED to OPEN
[2025-01-15 10:31:45] Circuit Breaker 'payment_api' transitioned from OPEN to HALF_OPEN
[2025-01-15 10:31:50] Circuit Breaker 'payment_api' transitioned from HALF_OPEN to CLOSED
```

### Asynchronous Circuit Breaker

```python
import logging
from fluxgate import AsyncCircuitBreaker
from fluxgate.listeners.log import LogListener

logging.basicConfig(level=logging.INFO)

cb = AsyncCircuitBreaker(
    name="async_api",
    ...,
    listeners=[LogListener()],
)
```

## Custom Log Levels {#custom-log-level}

To use different log levels, create a custom listener:

```python
import logging
import time
from fluxgate.interfaces import IListener
from fluxgate.signal import Signal
from fluxgate.state import StateEnum

class WarningLogListener(IListener):
    """Logs only OPEN state transitions at WARNING level"""

    def __call__(self, signal: Signal) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(signal.timestamp))
        message = (
            f"[{timestamp}] Circuit Breaker '{signal.circuit_name}' "
            f"transitioned from {signal.old_state.value} to {signal.new_state.value}"
        )

        if signal.new_state == StateEnum.OPEN:
            logging.warning(message)
        else:
            logging.info(message)
```

## Structured Logging {#structured-logging}

For JSON-formatted logs:

```python
import json
import logging
import time
from fluxgate.interfaces import IListener
from fluxgate.signal import Signal

class JsonLogListener(IListener):
    def __call__(self, signal: Signal) -> None:
        log_data = {
            "event": "circuit_breaker_transition",
            "circuit_name": signal.circuit_name,
            "old_state": signal.old_state.value,
            "new_state": signal.new_state.value,
            "timestamp": signal.timestamp,
        }
        logging.info(json.dumps(log_data))
```

## File Logging {#file-logging}

```python
import logging
from logging.handlers import RotatingFileHandler
from fluxgate.listeners.log import LogListener

handler = RotatingFileHandler(
    'circuit_breaker.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
))

logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.INFO)

cb = CircuitBreaker(..., listeners=[LogListener()])
```

## Next Steps {#next-steps}

- [PrometheusListener](prometheus.md) - Metrics-based monitoring
- [SlackListener](slack.md) - Real-time notifications
- [Overview](index.md) - Back to listeners overview
