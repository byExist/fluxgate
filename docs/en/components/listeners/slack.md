# SlackListener / AsyncSlackListener

The `SlackListener` and `AsyncSlackListener` push real-time notifications about circuit breaker state changes directly to a Slack channel. This is invaluable for immediately alerting on-call engineers when a critical service starts to fail, enabling a faster response.

## Installation {#installation}

This listener requires the `slack-sdk` library. You can install it as an extra:

```bash
pip install fluxgate[slack]
```

---

## Slack Setup {#slack-setup}

### 1. Create a Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps) and click **Create New App**.
2. Choose **From scratch**, enter an app name (e.g., "Circuit Breaker Alerts"), and select your workspace.

### 2. Add Bot Token Scopes

In the sidebar, go to **OAuth & Permissions** and scroll down to the "Scopes" section. Add the following **Bot Token Scopes**:

- `chat:write`: To send messages.
- `chat:write.public`: To send messages to public channels (optional).

### 3. Install the App and Copy the Token

1. Scroll back to the top of the **OAuth & Permissions** page and click **Install to Workspace**.
2. After installation, copy the **Bot User OAuth Token**. It will start with `xoxb-`.

### 4. Get the Channel ID and Invite the Bot

1. In your Slack client, right-click the channel where you want to receive alerts, select "View channel details," and copy the **Channel ID** from the bottom of the pop-up (e.g., `C1234567890`).
2. In the same channel, type `/invite @YourAppName` to add the bot to the channel so it has permission to post messages.

---

## Usage {#usage}

It is highly recommended to store your Slack token and channel ID as environment variables rather than hard-coding them in your source code.

### Synchronous (`SlackListener`)

Use `SlackListener` with a standard `CircuitBreaker`.

<!--pytest.mark.skip-->

```python
import os
from fluxgate import CircuitBreaker
from fluxgate.listeners.slack import SlackListener

slack_listener = SlackListener(
    channel=os.environ["SLACK_CHANNEL_ID"],
    token=os.environ["SLACK_BOT_TOKEN"]
)

cb = CircuitBreaker(
    name="payment_api",
    ...,
    listeners=[slack_listener],
)
```

### Asynchronous (`AsyncSlackListener`)

Use `AsyncSlackListener` with an `AsyncCircuitBreaker`. The underlying HTTP calls will be made asynchronously.

<!--pytest.mark.skip-->

```python
import os
from fluxgate import AsyncCircuitBreaker
from fluxgate.listeners.slack import AsyncSlackListener

slack_listener = AsyncSlackListener(
    channel=os.environ["SLACK_CHANNEL_ID"],
    token=os.environ["SLACK_BOT_TOKEN"]
)

cb = AsyncCircuitBreaker(
    name="async_api",
    ...,
    listeners=[slack_listener],
)
```

---

## Message Format {#message-format}

The listener sends threaded messages to keep conversations organized.

- **CLOSED → OPEN**
    - 🚨 **Circuit Breaker Triggered**
    - A red message is posted to the channel to start a new thread.
- **OPEN → HALF_OPEN**
    - 🔄 **Attempting Circuit Breaker Recovery**
    - An orange message is posted as a reply in the original thread.
- **HALF_OPEN → OPEN**
    - ⚠️ **Circuit Breaker Re-triggered**
    - A red message is posted as a reply, indicating the recovery attempt failed.
- **HALF_OPEN → CLOSED**
    - ✅ **Circuit Breaker Recovered**
    - A green message is posted as a reply and is also broadcast back to the main channel to confirm recovery.

---

## Advanced Usage

### Conditional Notifications {#conditional-notifications}

You may not want to be notified of every state change. To filter notifications, you can write a simple wrapper around the listener.

<!--pytest.mark.skip-->

```python
from fluxgate.interfaces import IListener
from fluxgate.signal import Signal
from fluxgate.state import StateEnum
from fluxgate.listeners.slack import SlackListener

class CriticalAlertListener(IListener):
    """A wrapper listener that only sends a notification when a circuit opens."""

    def __init__(self, channel: str, token: str):
        # The actual SlackListener that does the work
        self._slack = SlackListener(channel, token)

    def __call__(self, signal: Signal) -> None:
        # Only call the underlying listener if the new state is OPEN
        if signal.new_state == StateEnum.OPEN:
            self._slack(signal)
```

### Custom Messages {#custom-messages}

To completely customize the message format, you can write your own listener using the `slack_sdk`.

<!--pytest.mark.skip-->

```python
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from fluxgate.interfaces import IListener
from fluxgate.signal import Signal
from fluxgate.state import StateEnum

class CustomSlackListener(IListener):
    def __init__(self, channel: str, token: str):
        self.channel = channel
        self.client = WebClient(token=token)

    def __call__(self, signal: Signal) -> None:
        if signal.new_state != StateEnum.OPEN:
            return  # Only notify on OPEN

        try:
            message = f"Yo, the '{signal.circuit_name}' breaker just tripped. Check it out!"
            self.client.chat_postMessage(channel=self.channel, text=message)
        except SlackApiError as e:
            # It's important to handle errors so a listener failure
            # doesn't crash the main application.
            print(f"Error sending Slack notification: {e}")
```

---

## Troubleshooting {#troubleshooting}

- **`invalid_auth` error**: Your bot token is likely incorrect or has been revoked.
- **`not_in_channel` error**: You have not invited the bot to the channel. Type `/invite @YourAppName` in the channel.
- **`channel_not_found` error**: The channel ID is incorrect.
- **No messages appear**:
    - Check that the `chat:write` scope was added under **OAuth & Permissions**.
    - Ensure the app was re-installed to the workspace after scopes were changed.
    - Verify the circuit breaker is actually changing state.

## Next Steps {#next-steps}

- [PrometheusListener](prometheus.md): Set up metrics-based monitoring and alerting.
- [LogListener](logging.md): Configure detailed logging for all transitions.
- [Listeners Overview](index.md): Return to the main listeners page.
