import time
from typing import Any, ClassVar, Optional, TypedDict

import httpx

from fluxgate.listeners import AsyncListener, Listener
from fluxgate.signal import Signal
from fluxgate.state import State

__all__ = ["SlackListener", "AsyncSlackListener", "Template"]


class Template(TypedDict):
    title: str
    color: str
    description: str


_DEFAULT_TRANSITION_TEMPLATES: dict[tuple[State, State], Template] = {
    ("closed", "open"): {
        "title": "🚨 Circuit Breaker Triggered",
        "color": "#FF4C4C",
        "description": "The request failure rate exceeded the threshold.",
    },
    ("open", "half_open"): {
        "title": "🔄 Attempting Circuit Breaker Recovery",
        "color": "#FFA500",
        "description": "Testing service status with partial requests.",
    },
    ("half_open", "open"): {
        "title": "⚠️ Circuit Breaker Re-triggered",
        "color": "#FF4C4C",
        "description": "Test request failed, reverting to open state.",
    },
    ("half_open", "closed"): {
        "title": "✅ Circuit Breaker Recovered",
        "color": "#36a64f",
        "description": "Test request succeeded, service is now healthy.",
    },
}

_DEFAULT_FALLBACK_TEMPLATE: Template = {
    "title": "ℹ️ Circuit Breaker State Changed",
    "color": "#808080",
    "description": "Circuit breaker state has been changed.",
}


_SLACK_POST_URL = "https://slack.com/api/chat.postMessage"
_THREAD_CLEAR_STATES = ("closed", "disabled", "metrics_only")


def _build_message(
    channel: str,
    name: str,
    signal: Signal,
    template: Template,
    thread: Optional[str] = None,
) -> dict[str, Any]:
    """Build Slack message payload."""
    payload: dict[str, Any] = {
        "channel": channel,
        "attachments": [
            {
                "color": template["color"],
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*{template['title']}*"},
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Circuit Breaker:*\n{name}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*State Transition:*\n{signal.old_state} → {signal.new_state}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Transition Time:*\n{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(signal.timestamp))}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Description:*\n{template['description']}",
                            },
                        ],
                    },
                ],
            }
        ],
    }
    if thread:
        payload["thread_ts"] = thread
    if signal.new_state == "closed":
        payload["reply_broadcast"] = True
    return payload


class _SlackBase:
    """Shared template, payload, and thread-tracking logic for Slack listeners.

    Subclasses own the HTTP client and define ``__call__`` for their concurrency
    model (sync ``def`` or ``async def``).
    """

    TRANSITION_TEMPLATES: ClassVar[dict[tuple[State, State], Template]] = (
        _DEFAULT_TRANSITION_TEMPLATES
    )
    FALLBACK_TEMPLATE: ClassVar[Template] = _DEFAULT_FALLBACK_TEMPLATE

    def __init__(self, name: str, channel: str) -> None:
        self._name = name
        self._channel = channel
        self._open_thread: Optional[str] = None

    def _build_payload(self, signal: Signal) -> dict[str, Any]:
        template = self.TRANSITION_TEMPLATES.get(
            (signal.old_state, signal.new_state), self.FALLBACK_TEMPLATE
        )
        return _build_message(
            channel=self._channel,
            name=self._name,
            signal=signal,
            template=template,
            thread=self._open_thread,
        )

    def _consume_response(self, signal: Signal, data: dict[str, Any]) -> None:
        ts = data.get("ts")
        if not data.get("ok") or not ts:
            raise RuntimeError(f"Failed to send message: {data.get('error')}")
        if signal.new_state == "open":
            if self._open_thread is None:
                self._open_thread = ts
        elif signal.new_state in _THREAD_CLEAR_STATES:
            self._open_thread = None


class SlackListener(_SlackBase, Listener):
    """Listener that sends circuit breaker state transitions to Slack.

    Posts formatted messages to a Slack channel when state transitions occur.
    Groups related transitions into threads based on failure cycles:

    - Thread starts on → OPEN (new or continued failure cycle)
    - Thread ends on → CLOSED, DISABLED, or METRICS_ONLY

    Args:
        name: Identifier shown in the Slack message body.
        channel: Slack channel ID (e.g., "C1234567890") or name (e.g., "#alerts")
        token: Slack bot token with chat:write permissions

    Class Attributes:
        TRANSITION_TEMPLATES: Override to customize messages for specific transitions.
        FALLBACK_TEMPLATE: Override to customize the default message for other transitions.

    Examples:
        >>> from fluxgate import CircuitBreaker
        >>> from fluxgate.listeners.slack import SlackListener
        >>>
        >>> listener = SlackListener(
        ...     name="api",
        ...     channel="C1234567890",
        ...     token="xoxb-your-slack-bot-token"
        ... )
        >>>
        >>> cb = CircuitBreaker(listeners=[listener])

        To customize messages (e.g., for Korean):

        >>> class KoreanSlackListener(SlackListener):
        ...     TRANSITION_TEMPLATES = {
        ...         ("closed", "open"): {
        ...             "title": "🚨 서킷 브레이커 작동",
        ...             "color": "#FF4C4C",
        ...             "description": "요청 실패율이 임계값을 초과했습니다.",
        ...         },
        ...         # ... other transitions
        ...     }
        ...     FALLBACK_TEMPLATE = {
        ...         "title": "ℹ️ 서킷 브레이커 상태 변경",
        ...         "color": "#808080",
        ...         "description": "서킷 브레이커 상태가 변경되었습니다.",
        ...     }
    """

    def __init__(self, name: str, channel: str, token: str) -> None:
        super().__init__(name, channel)
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )

    def __call__(self, signal: Signal) -> None:
        payload = self._build_payload(signal)
        response = self._client.post(_SLACK_POST_URL, json=payload)
        response.raise_for_status()
        self._consume_response(signal, response.json())


class AsyncSlackListener(_SlackBase, AsyncListener):
    """Async listener that sends circuit breaker state transitions to Slack.

    Posts formatted messages to a Slack channel when state transitions occur.
    Groups related transitions into threads based on failure cycles:

    - Thread starts on → OPEN (new or continued failure cycle)
    - Thread ends on → CLOSED, DISABLED, or METRICS_ONLY

    Args:
        name: Identifier shown in the Slack message body.
        channel: Slack channel ID (e.g., "C1234567890") or name (e.g., "#alerts")
        token: Slack bot token with chat:write permissions

    Class Attributes:
        TRANSITION_TEMPLATES: Override to customize messages for specific transitions.
        FALLBACK_TEMPLATE: Override to customize the default message for other transitions.

    Note:
        Uses httpx for async HTTP requests.

    Examples:
        >>> from fluxgate import AsyncCircuitBreaker
        >>> from fluxgate.listeners.slack import AsyncSlackListener
        >>>
        >>> listener = AsyncSlackListener(
        ...     name="api",
        ...     channel="C1234567890",
        ...     token="xoxb-your-slack-bot-token"
        ... )
        >>>
        >>> cb = AsyncCircuitBreaker(listeners=[listener])
    """

    def __init__(self, name: str, channel: str, token: str) -> None:
        super().__init__(name, channel)
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )

    async def __call__(self, signal: Signal) -> None:
        payload = self._build_payload(signal)
        response = await self._client.post(_SLACK_POST_URL, json=payload)
        response.raise_for_status()
        self._consume_response(signal, response.json())
