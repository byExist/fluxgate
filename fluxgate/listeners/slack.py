import time
from typing import Any, ClassVar, Optional, TypedDict

import httpx

from fluxgate.interfaces import IListener, IAsyncListener
from fluxgate.signal import Signal
from fluxgate.state import StateEnum

__all__ = ["SlackListener", "AsyncSlackListener", "Template"]


class Template(TypedDict):
    title: str
    color: str
    description: str


_DEFAULT_TRANSITION_TEMPLATES: dict[tuple[StateEnum, StateEnum], Template] = {
    (StateEnum.CLOSED, StateEnum.OPEN): {
        "title": "🚨 Circuit Breaker Triggered",
        "color": "#FF4C4C",
        "description": "The request failure rate exceeded the threshold.",
    },
    (StateEnum.OPEN, StateEnum.HALF_OPEN): {
        "title": "🔄 Attempting Circuit Breaker Recovery",
        "color": "#FFA500",
        "description": "Testing service status with partial requests.",
    },
    (StateEnum.HALF_OPEN, StateEnum.OPEN): {
        "title": "⚠️ Circuit Breaker Re-triggered",
        "color": "#FF4C4C",
        "description": "Test request failed, reverting to open state.",
    },
    (StateEnum.HALF_OPEN, StateEnum.CLOSED): {
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


def _build_message(
    channel: str,
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
                                "text": f"*Circuit Breaker:*\n{signal.circuit_name}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*State Transition:*\n{signal.old_state.value} → {signal.new_state.value}",
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
    if signal.new_state == StateEnum.CLOSED:
        payload["reply_broadcast"] = True
    return payload


class SlackListener(IListener):
    """Listener that sends circuit breaker state transitions to Slack.

    Posts formatted messages to a Slack channel when state transitions occur.
    Groups related transitions into threads based on failure cycles:

    - Thread starts on → OPEN (new or continued failure cycle)
    - Thread ends on → CLOSED, DISABLED, or METRICS_ONLY

    Args:
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
        ...     channel="C1234567890",
        ...     token="xoxb-your-slack-bot-token"
        ... )
        >>>
        >>> cb = CircuitBreaker(..., listeners=[listener])

        To customize messages (e.g., for Korean):

        >>> class KoreanSlackListener(SlackListener):
        ...     TRANSITION_TEMPLATES = {
        ...         (StateEnum.CLOSED, StateEnum.OPEN): {
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

    TRANSITION_TEMPLATES: ClassVar[dict[tuple[StateEnum, StateEnum], Template]] = (
        _DEFAULT_TRANSITION_TEMPLATES
    )
    FALLBACK_TEMPLATE: ClassVar[Template] = _DEFAULT_FALLBACK_TEMPLATE

    def __init__(self, channel: str, token: str) -> None:
        self._channel = channel
        self._token = token
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        self._open_threads: dict[str, str] = {}

    def _get_template(self, old_state: StateEnum, new_state: StateEnum) -> Template:
        """Get message template with fallback for unknown transitions."""
        return self.TRANSITION_TEMPLATES.get(
            (old_state, new_state), self.FALLBACK_TEMPLATE
        )

    def __call__(self, signal: Signal) -> None:
        template = self._get_template(signal.old_state, signal.new_state)
        message = _build_message(
            channel=self._channel,
            signal=signal,
            template=template,
            thread=self._open_threads.get(signal.circuit_name),
        )
        response = self._client.post(
            "https://slack.com/api/chat.postMessage", json=message
        )
        response.raise_for_status()
        data = response.json()
        ts = data.get("ts")
        if not data.get("ok") or not ts:
            raise RuntimeError(f"Failed to send message: {data.get('error')}")
        if signal.new_state == StateEnum.OPEN:
            self._open_threads.setdefault(signal.circuit_name, ts)
        elif signal.new_state in (
            StateEnum.CLOSED,
            StateEnum.DISABLED,
            StateEnum.METRICS_ONLY,
        ):
            self._open_threads.pop(signal.circuit_name, None)


class AsyncSlackListener(IAsyncListener):
    """Async listener that sends circuit breaker state transitions to Slack.

    Posts formatted messages to a Slack channel when state transitions occur.
    Groups related transitions into threads based on failure cycles:

    - Thread starts on → OPEN (new or continued failure cycle)
    - Thread ends on → CLOSED, DISABLED, or METRICS_ONLY

    Args:
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
        ...     channel="C1234567890",
        ...     token="xoxb-your-slack-bot-token"
        ... )
        >>>
        >>> cb = AsyncCircuitBreaker(..., listeners=[listener])
    """

    TRANSITION_TEMPLATES: ClassVar[dict[tuple[StateEnum, StateEnum], Template]] = (
        SlackListener.TRANSITION_TEMPLATES
    )
    FALLBACK_TEMPLATE: ClassVar[Template] = SlackListener.FALLBACK_TEMPLATE

    def __init__(self, channel: str, token: str) -> None:
        self._channel = channel
        self._token = token
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        self._open_threads: dict[str, str] = {}

    def _get_template(self, old_state: StateEnum, new_state: StateEnum) -> Template:
        """Get message template with fallback for unknown transitions."""
        return self.TRANSITION_TEMPLATES.get(
            (old_state, new_state), self.FALLBACK_TEMPLATE
        )

    async def __call__(self, signal: Signal) -> None:
        template = self._get_template(signal.old_state, signal.new_state)
        message = _build_message(
            channel=self._channel,
            signal=signal,
            template=template,
            thread=self._open_threads.get(signal.circuit_name),
        )
        response = await self._client.post(
            "https://slack.com/api/chat.postMessage", json=message
        )
        response.raise_for_status()
        data = response.json()
        ts = data.get("ts")
        if not data.get("ok") or not ts:
            raise RuntimeError(f"Failed to send message: {data.get('error')}")
        if signal.new_state == StateEnum.OPEN:
            self._open_threads.setdefault(signal.circuit_name, ts)
        elif signal.new_state in (
            StateEnum.CLOSED,
            StateEnum.DISABLED,
            StateEnum.METRICS_ONLY,
        ):
            self._open_threads.pop(signal.circuit_name, None)
