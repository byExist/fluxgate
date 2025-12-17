"""Tests for SlackListener."""

from typing import Any
from unittest.mock import Mock, AsyncMock, patch

import pytest

from fluxgate.signal import Signal
from fluxgate.state import StateEnum

pytest.importorskip("httpx")

from fluxgate.listeners.slack import SlackListener, AsyncSlackListener


@pytest.fixture
def mock_slack_response() -> Mock:
    """Create a mock Slack API response."""
    response = Mock()
    response.json.return_value = {"ok": True, "ts": "1234.5678"}
    return response


@pytest.fixture
def mock_sync_client(mock_slack_response: Mock):
    """Create a mock sync httpx client."""
    with patch("httpx.Client") as mock_client_class:
        mock_client = Mock()
        mock_client.post.return_value = mock_slack_response
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_async_client(mock_slack_response: Mock):
    """Create a mock async httpx client."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_slack_response
        mock_client_class.return_value = mock_client
        yield mock_client


def get_posted_json(mock_client: Mock, call_index: int = 0) -> dict[str, Any]:
    """Extract the JSON payload from a mock client's post call."""
    return mock_client.post.call_args_list[call_index][1]["json"]


def test_closed_to_open_sends_triggered_message(mock_sync_client: Mock):
    """CLOSED -> OPEN sends triggered message."""
    listener = SlackListener(channel="#alerts", token="xoxb-test")
    signal = Signal(
        circuit_name="api",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
        timestamp=1234567890.0,
    )

    listener(signal)

    payload = get_posted_json(mock_sync_client)
    assert payload["channel"] == "#alerts"
    assert "🚨 Circuit Breaker Triggered" in str(payload)
    assert "api" in str(payload)


def test_open_to_half_open_sends_recovery_attempt_message(mock_sync_client: Mock):
    """OPEN -> HALF_OPEN sends recovery attempt message."""
    listener = SlackListener(channel="#alerts", token="xoxb-test")
    signal = Signal(
        circuit_name="api",
        old_state=StateEnum.OPEN,
        new_state=StateEnum.HALF_OPEN,
        timestamp=1.0,
    )

    listener(signal)

    payload = get_posted_json(mock_sync_client)
    assert "🔄 Attempting Circuit Breaker Recovery" in str(payload)


def test_half_open_to_open_sends_re_triggered_message(mock_sync_client: Mock):
    """HALF_OPEN -> OPEN sends re-triggered message."""
    listener = SlackListener(channel="#alerts", token="xoxb-test")
    signal = Signal(
        circuit_name="api",
        old_state=StateEnum.HALF_OPEN,
        new_state=StateEnum.OPEN,
        timestamp=1.0,
    )

    listener(signal)

    payload = get_posted_json(mock_sync_client)
    assert "⚠️ Circuit Breaker Re-triggered" in str(payload)


def test_half_open_to_closed_sends_recovered_message(mock_sync_client: Mock):
    """HALF_OPEN -> CLOSED sends recovered message with broadcast."""
    listener = SlackListener(channel="#alerts", token="xoxb-test")
    signal = Signal(
        circuit_name="api",
        old_state=StateEnum.HALF_OPEN,
        new_state=StateEnum.CLOSED,
        timestamp=1.0,
    )

    listener(signal)

    payload = get_posted_json(mock_sync_client)
    assert "✅ Circuit Breaker Recovered" in str(payload)
    assert payload.get("reply_broadcast") is True


def test_unknown_transition_sends_fallback_message(mock_sync_client: Mock):
    """Unknown transition sends fallback message."""
    listener = SlackListener(channel="#alerts", token="xoxb-test")
    signal = Signal(
        circuit_name="api",
        old_state=StateEnum.DISABLED,
        new_state=StateEnum.CLOSED,
        timestamp=1.0,
    )

    listener(signal)

    payload = get_posted_json(mock_sync_client)
    assert "ℹ️ Circuit Breaker State Changed" in str(payload)


def test_open_transition_starts_new_thread(mock_sync_client: Mock):
    """First CLOSED -> OPEN starts a new thread (no thread_ts)."""
    listener = SlackListener(channel="#alerts", token="xoxb-test")
    signal = Signal(
        circuit_name="api",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
        timestamp=1.0,
    )

    listener(signal)

    payload = get_posted_json(mock_sync_client)
    assert "thread_ts" not in payload


def test_subsequent_transitions_use_thread(mock_sync_client: Mock):
    """Subsequent transitions use the thread started by CLOSED -> OPEN."""
    listener = SlackListener(channel="#alerts", token="xoxb-test")

    # First: CLOSED -> OPEN
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.CLOSED,
            new_state=StateEnum.OPEN,
            timestamp=1.0,
        )
    )

    # Second: OPEN -> HALF_OPEN
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.OPEN,
            new_state=StateEnum.HALF_OPEN,
            timestamp=2.0,
        )
    )

    payload = get_posted_json(mock_sync_client, 1)
    assert payload["thread_ts"] == "1234.5678"


def test_recovery_clears_thread(mock_sync_client: Mock):
    """Recovery (HALF_OPEN -> CLOSED) clears thread for next incident."""
    listener = SlackListener(channel="#alerts", token="xoxb-test")

    # Start thread
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.CLOSED,
            new_state=StateEnum.OPEN,
            timestamp=1.0,
        )
    )

    # Recover
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.HALF_OPEN,
            new_state=StateEnum.CLOSED,
            timestamp=2.0,
        )
    )

    # New incident
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.CLOSED,
            new_state=StateEnum.OPEN,
            timestamp=3.0,
        )
    )

    payload = get_posted_json(mock_sync_client, 2)
    assert "thread_ts" not in payload


def test_separate_circuits_have_separate_threads(mock_sync_client: Mock):
    """Different circuits don't share threads."""
    listener = SlackListener(channel="#alerts", token="xoxb-test")

    # Circuit A opens
    listener(
        Signal(
            circuit_name="circuit_a",
            old_state=StateEnum.CLOSED,
            new_state=StateEnum.OPEN,
            timestamp=1.0,
        )
    )

    # Circuit B opens
    listener(
        Signal(
            circuit_name="circuit_b",
            old_state=StateEnum.CLOSED,
            new_state=StateEnum.OPEN,
            timestamp=2.0,
        )
    )

    payload_b = get_posted_json(mock_sync_client, 1)
    assert "thread_ts" not in payload_b


def test_raises_on_api_error(mock_sync_client: Mock):
    """Raises RuntimeError on Slack API error."""
    mock_sync_client.post.return_value.json.return_value = {
        "ok": False,
        "error": "channel_not_found",
    }

    listener = SlackListener(channel="#invalid", token="xoxb-test")
    signal = Signal(
        circuit_name="api",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
        timestamp=1.0,
    )

    with pytest.raises(RuntimeError, match="Failed to send message"):
        listener(signal)


async def test_async_listener_sends_message(mock_async_client: AsyncMock):
    """AsyncSlackListener sends message to Slack."""
    listener = AsyncSlackListener(channel="#alerts", token="xoxb-test")
    signal = Signal(
        circuit_name="api",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
        timestamp=1.0,
    )

    await listener(signal)

    mock_async_client.post.assert_called_once()
    payload = get_posted_json(mock_async_client)
    assert payload["channel"] == "#alerts"
    assert "🚨 Circuit Breaker Triggered" in str(payload)


async def test_async_listener_threading(mock_async_client: AsyncMock):
    """AsyncSlackListener threads messages correctly."""
    listener = AsyncSlackListener(channel="#alerts", token="xoxb-test")

    # First: CLOSED -> OPEN
    await listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.CLOSED,
            new_state=StateEnum.OPEN,
            timestamp=1.0,
        )
    )

    # Second: OPEN -> HALF_OPEN
    await listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.OPEN,
            new_state=StateEnum.HALF_OPEN,
            timestamp=2.0,
        )
    )

    payload = get_posted_json(mock_async_client, 1)
    assert payload["thread_ts"] == "1234.5678"


def test_reset_from_open_clears_thread(mock_sync_client: Mock):
    """Direct reset (OPEN -> CLOSED) clears thread."""
    listener = SlackListener(channel="#alerts", token="xoxb-test")

    # Start thread
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.CLOSED,
            new_state=StateEnum.OPEN,
            timestamp=1.0,
        )
    )

    # Direct reset (skipping HALF_OPEN)
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.OPEN,
            new_state=StateEnum.CLOSED,
            timestamp=2.0,
        )
    )

    # New incident should start fresh thread
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.CLOSED,
            new_state=StateEnum.OPEN,
            timestamp=3.0,
        )
    )

    payload = get_posted_json(mock_sync_client, 2)
    assert "thread_ts" not in payload


def test_disable_clears_thread(mock_sync_client: Mock):
    """Transition to DISABLED clears thread."""
    listener = SlackListener(channel="#alerts", token="xoxb-test")

    # Start thread
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.CLOSED,
            new_state=StateEnum.OPEN,
            timestamp=1.0,
        )
    )

    # Disable circuit
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.OPEN,
            new_state=StateEnum.DISABLED,
            timestamp=2.0,
        )
    )

    # Re-enable and new incident
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.DISABLED,
            new_state=StateEnum.CLOSED,
            timestamp=3.0,
        )
    )
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.CLOSED,
            new_state=StateEnum.OPEN,
            timestamp=4.0,
        )
    )

    payload = get_posted_json(mock_sync_client, 3)
    assert "thread_ts" not in payload


def test_metrics_only_clears_thread(mock_sync_client: Mock):
    """Transition to METRICS_ONLY clears thread."""
    listener = SlackListener(channel="#alerts", token="xoxb-test")

    # Start thread
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.CLOSED,
            new_state=StateEnum.OPEN,
            timestamp=1.0,
        )
    )

    # Switch to metrics only
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.OPEN,
            new_state=StateEnum.METRICS_ONLY,
            timestamp=2.0,
        )
    )

    # Re-enable and new incident
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.METRICS_ONLY,
            new_state=StateEnum.CLOSED,
            timestamp=3.0,
        )
    )
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.CLOSED,
            new_state=StateEnum.OPEN,
            timestamp=4.0,
        )
    )

    payload = get_posted_json(mock_sync_client, 3)
    assert "thread_ts" not in payload


def test_forced_open_keeps_thread(mock_sync_client: Mock):
    """Transition to FORCED_OPEN keeps thread (failure cycle continues)."""
    listener = SlackListener(channel="#alerts", token="xoxb-test")

    # Start thread
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.CLOSED,
            new_state=StateEnum.OPEN,
            timestamp=1.0,
        )
    )

    # Force open (manual intervention)
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.OPEN,
            new_state=StateEnum.FORCED_OPEN,
            timestamp=2.0,
        )
    )

    # Message should still be in thread
    payload = get_posted_json(mock_sync_client, 1)
    assert payload["thread_ts"] == "1234.5678"


def test_reset_from_forced_open_clears_thread(mock_sync_client: Mock):
    """Reset from FORCED_OPEN clears thread."""
    listener = SlackListener(channel="#alerts", token="xoxb-test")

    # Start thread
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.CLOSED,
            new_state=StateEnum.OPEN,
            timestamp=1.0,
        )
    )

    # Force open
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.OPEN,
            new_state=StateEnum.FORCED_OPEN,
            timestamp=2.0,
        )
    )

    # Reset
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.FORCED_OPEN,
            new_state=StateEnum.CLOSED,
            timestamp=3.0,
        )
    )

    # New incident should start fresh
    listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.CLOSED,
            new_state=StateEnum.OPEN,
            timestamp=4.0,
        )
    )

    payload = get_posted_json(mock_sync_client, 3)
    assert "thread_ts" not in payload


async def test_async_reset_from_open_clears_thread(mock_async_client: AsyncMock):
    """Direct reset (OPEN -> CLOSED) clears thread."""
    listener = AsyncSlackListener(channel="#alerts", token="xoxb-test")

    # Start thread
    await listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.CLOSED,
            new_state=StateEnum.OPEN,
            timestamp=1.0,
        )
    )

    # Direct reset
    await listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.OPEN,
            new_state=StateEnum.CLOSED,
            timestamp=2.0,
        )
    )

    # New incident
    await listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.CLOSED,
            new_state=StateEnum.OPEN,
            timestamp=3.0,
        )
    )

    payload = get_posted_json(mock_async_client, 2)
    assert "thread_ts" not in payload


async def test_async_disable_clears_thread(mock_async_client: AsyncMock):
    """Transition to DISABLED clears thread."""
    listener = AsyncSlackListener(channel="#alerts", token="xoxb-test")

    # Start thread
    await listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.CLOSED,
            new_state=StateEnum.OPEN,
            timestamp=1.0,
        )
    )

    # Disable
    await listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.OPEN,
            new_state=StateEnum.DISABLED,
            timestamp=2.0,
        )
    )

    # Re-enable and new incident
    await listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.DISABLED,
            new_state=StateEnum.CLOSED,
            timestamp=3.0,
        )
    )
    await listener(
        Signal(
            circuit_name="api",
            old_state=StateEnum.CLOSED,
            new_state=StateEnum.OPEN,
            timestamp=4.0,
        )
    )

    payload = get_posted_json(mock_async_client, 3)
    assert "thread_ts" not in payload
