import time
from typing import Any, Optional

import httpx

from fluxgate.interfaces import IListener, IAsyncListener
from fluxgate.signal import Signal
from fluxgate.state import StateEnum

__all__ = ["SlackListener", "AsyncSlackListener"]


_TRANSITION_MESSAGE_DATA: dict[tuple[StateEnum, StateEnum], dict[str, str]] = {
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


def _build_message(
    channel: str,
    signal: Signal,
    thread: Optional[str] = None,
):
    transition = (signal.old_state, signal.new_state)
    template = _TRANSITION_MESSAGE_DATA[transition]
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
    Groups related transitions into threads (OPEN → HALF_OPEN → CLOSED).

    Args:
        channel: Slack channel ID (e.g., "C1234567890") or name (e.g., "#alerts")
        token: Slack bot token with chat:write permissions

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
    """

    def __init__(self, channel: str, token: str) -> None:
        self._channel = channel
        self._token = token
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        self._open_threads: dict[str, str] = {}

    def __call__(self, signal: Signal) -> None:
        message = _build_message(
            channel=self._channel,
            signal=signal,
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
        transition = (signal.old_state, signal.new_state)
        if transition == (StateEnum.CLOSED, StateEnum.OPEN):
            self._open_threads[signal.circuit_name] = ts
        elif transition == (StateEnum.HALF_OPEN, StateEnum.CLOSED):
            self._open_threads.pop(signal.circuit_name, None)


class AsyncSlackListener(IAsyncListener):
    """Async listener that sends circuit breaker state transitions to Slack.

    Posts formatted messages to a Slack channel when state transitions occur.
    Groups related transitions into threads (OPEN → HALF_OPEN → CLOSED).

    Args:
        channel: Slack channel ID (e.g., "C1234567890") or name (e.g., "#alerts")
        token: Slack bot token with chat:write permissions

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

    def __init__(self, channel: str, token: str) -> None:
        self._channel = channel
        self._token = token
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        self._open_threads: dict[str, str] = {}

    async def __call__(self, signal: Signal) -> None:
        message = _build_message(
            channel=self._channel,
            signal=signal,
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
        transition = (signal.old_state, signal.new_state)
        if transition == (StateEnum.CLOSED, StateEnum.OPEN):
            self._open_threads[signal.circuit_name] = ts
        elif transition == (StateEnum.HALF_OPEN, StateEnum.CLOSED):
            self._open_threads.pop(signal.circuit_name, None)
