# SlackListener / AsyncSlackListener

The `SlackListener` and `AsyncSlackListener` push real-time notifications about circuit breaker state changes directly to a Slack channel. This is invaluable for immediately alerting on-call engineers when a critical service starts to fail, enabling a faster response.

## Installation {#installation}

This listener requires `httpx` for HTTP requests. You can install it as an extra:

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

The listener sends threaded messages to keep conversations organized based on failure cycles:

- **Thread starts** on any transition **→ OPEN** (new or continued failure cycle)
- **Thread ends** on transition to **→ CLOSED**, **→ DISABLED**, or **→ METRICS_ONLY**

| Transition | Title | Color | Description |
|---|---|---|---|
| CLOSED → OPEN | 🚨 Circuit Breaker Triggered | Red | Starts a new thread |
| OPEN → HALF_OPEN | 🔄 Attempting Circuit Breaker Recovery | Orange | Reply in thread |
| HALF_OPEN → OPEN | ⚠️ Circuit Breaker Re-triggered | Red | Reply in thread (thread continues) |
| HALF_OPEN → CLOSED | ✅ Circuit Breaker Recovered | Green | Reply + broadcast, then clears thread |
| Any other | ℹ️ Circuit Breaker State Changed | Gray | Fallback for manual transitions |

Transitions to `CLOSED`, `DISABLED`, or `METRICS_ONLY` end the current thread, so the next failure cycle starts a fresh thread. Transitions to `FORCED_OPEN` keep the thread open since the failure cycle continues.

---

## Advanced Usage

### Custom Messages {#custom-messages}

To customize message templates (e.g., for different languages), you can subclass `SlackListener` and override the class attributes.

Each template is a `Template` TypedDict with three required keys:

- `title`: The message title (supports emoji)
- `color`: Hex color code for the attachment sidebar
- `description`: Detailed description of the state change

<!--pytest.mark.skip-->

```python
from fluxgate.listeners.slack import SlackListener, Template
from fluxgate.state import StateEnum

class KoreanSlackListener(SlackListener):
    """SlackListener with Korean messages."""

    TRANSITION_TEMPLATES: dict[tuple[StateEnum, StateEnum], Template] = {
        (StateEnum.CLOSED, StateEnum.OPEN): {
            "title": "🚨 서킷 브레이커 작동",
            "color": "#FF4C4C",
            "description": "요청 실패율이 임계값을 초과했습니다.",
        },
        (StateEnum.OPEN, StateEnum.HALF_OPEN): {
            "title": "🔄 서킷 브레이커 복구 시도 중",
            "color": "#FFA500",
            "description": "부분 요청으로 서비스 상태를 테스트하고 있습니다.",
        },
        (StateEnum.HALF_OPEN, StateEnum.OPEN): {
            "title": "⚠️ 서킷 브레이커 재작동",
            "color": "#FF4C4C",
            "description": "테스트 요청이 실패하여 열림 상태로 복귀합니다.",
        },
        (StateEnum.HALF_OPEN, StateEnum.CLOSED): {
            "title": "✅ 서킷 브레이커 복구됨",
            "color": "#36a64f",
            "description": "테스트 요청이 성공하여 서비스가 정상입니다.",
        },
    }

    FALLBACK_TEMPLATE: Template = {
        "title": "ℹ️ 서킷 브레이커 상태 변경",
        "color": "#808080",
        "description": "서킷 브레이커 상태가 변경되었습니다.",
    }
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
