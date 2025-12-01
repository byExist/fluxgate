# SlackListener / AsyncSlackListener

Listeners that send circuit breaker state transition notifications to Slack channels.

## Installation {#installation}

```bash
pip install fluxgate[slack]
```

## Slack Setup {#slack-setup}

### 1. Create Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps) and click "Create New App"
2. Select "From scratch"
3. Enter app name and select workspace

### 2. Configure Bot Token Permissions

On the **OAuth & Permissions** page, add these scopes:

- `chat:write` - Send messages
- `chat:write.public` - Send messages to public channels (optional)

### 3. Copy Bot Token

**OAuth & Permissions** → **Bot User OAuth Token** (starts with xoxb-)

### 4. Get Channel ID

Right-click channel → "View channel details" → Copy Channel ID (e.g., C1234567890)

## Usage {#usage}

### Synchronous Circuit Breaker

```python
import os
from fluxgate import CircuitBreaker
from fluxgate.listeners.slack import SlackListener

slack = SlackListener(
    channel=os.environ["SLACK_CHANNEL"],
    token=os.environ["SLACK_BOT_TOKEN"]
)

cb = CircuitBreaker(
    name="payment_api",
    ...,
    listeners=[slack],
)
```

### Asynchronous Circuit Breaker

```python
import os
from fluxgate import AsyncCircuitBreaker
from fluxgate.listeners.slack import AsyncSlackListener

slack = AsyncSlackListener(
    channel=os.environ["SLACK_CHANNEL"],
    token=os.environ["SLACK_BOT_TOKEN"]
)

cb = AsyncCircuitBreaker(
    name="async_api",
    ...,
    listeners=[slack],
)
```

## Message Format {#message-format}

### CLOSED → OPEN

- 🚨 Circuit Breaker Triggered
- Red (#FF4C4C)
- Starts new thread

### OPEN → HALF_OPEN

- 🔄 Attempting Circuit Breaker Recovery
- Orange (#FFA500)
- Reply to same thread

### HALF_OPEN → OPEN

- ⚠️ Circuit Breaker Re-triggered
- Red (#FF4C4C)
- Reply to same thread

### HALF_OPEN → CLOSED

- ✅ Circuit Breaker Recovered
- Green (#36a64f)
- Reply to same thread + broadcast to channel

## Conditional Notifications {#conditional-notifications}

Only notify for specific state transitions:

```python
from fluxgate.interfaces import IListener
from fluxgate.signal import Signal
from fluxgate.state import StateEnum
from fluxgate.listeners.slack import SlackListener

class CriticalSlackListener(IListener):
    """Only notify on OPEN state transitions"""

    def __init__(self, channel: str, token: str):
        self._slack = SlackListener(channel, token)

    def __call__(self, signal: Signal) -> None:
        if signal.new_state == StateEnum.OPEN:
            self._slack(signal)
```

## Custom Messages {#custom-messages}

To customize message format, implement `IListener` directly. See [Slack API documentation](https://api.slack.com/messaging/composing) for message formatting.

## Troubleshooting {#troubleshooting}

- **401 Unauthorized**: Verify bot token
- **403 Forbidden**: Check `chat:write` permission and workspace installation
- **404 Channel Not Found**: Verify channel ID and bot invitation

## Next Steps {#next-steps}

- [PrometheusListener](prometheus.md) - Metrics-based monitoring
- [LogListener](logging.md) - Logging configuration
- [Overview](index.md) - Back to listeners overview
