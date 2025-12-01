"""Tests for SlackListener."""

from unittest.mock import Mock, AsyncMock, MagicMock, patch

import pytest

from fluxgate.signal import Signal
from fluxgate.state import StateEnum

pytest.importorskip("httpx")

from fluxgate.listeners.slack import (
    SlackListener,
    AsyncSlackListener,
    _build_message,  # type: ignore
)


def test_build_message_closed_to_open():
    """_build_message creates correct payload for CLOSED->OPEN transition."""
    signal = Signal(
        circuit_name="test_circuit",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
        timestamp=1234567890.0,
    )

    message = _build_message(channel="#alerts", signal=signal)

    assert message["channel"] == "#alerts"
    assert len(message["attachments"]) == 1
    attachment = message["attachments"][0]
    assert attachment["color"] == "#FF4C4C"
    assert "🚨 Circuit Breaker Triggered" in str(attachment)
    assert "test_circuit" in str(attachment)


def test_build_message_with_thread():
    """_build_message includes thread_ts when provided."""
    signal = Signal(
        circuit_name="test",
        old_state=StateEnum.OPEN,
        new_state=StateEnum.HALF_OPEN,
        timestamp=1.0,
    )

    message = _build_message(channel="#test", signal=signal, thread="1234.5678")

    assert message["thread_ts"] == "1234.5678"


def test_build_message_recovery_broadcasts():
    """_build_message sets reply_broadcast for recovery transitions."""
    signal = Signal(
        circuit_name="test",
        old_state=StateEnum.HALF_OPEN,
        new_state=StateEnum.CLOSED,
        timestamp=1.0,
    )

    message = _build_message(channel="#test", signal=signal)

    assert message["reply_broadcast"] is True


@patch("httpx.Client")
def test_slack_listener_basic(mock_client_class: MagicMock) -> None:
    """SlackListener sends messages to Slack API."""
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    mock_response = Mock()
    mock_response.json.return_value = {"ok": True, "ts": "1234.5678"}
    mock_client.post.return_value = mock_response

    listener = SlackListener(channel="#alerts", token="xoxb-test-token")

    signal = Signal(
        circuit_name="test",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
        timestamp=1.0,
    )

    listener(signal)

    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "https://slack.com/api/chat.postMessage"
    assert call_args[1]["json"]["channel"] == "#alerts"


@patch("httpx.Client")
def test_slack_listener_threading(mock_client_class: MagicMock) -> None:
    """SlackListener tracks threads for related transitions."""
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    mock_response = Mock()
    mock_response.json.return_value = {"ok": True, "ts": "1234.5678"}
    mock_client.post.return_value = mock_response

    listener = SlackListener(channel="#test", token="xoxb-test")

    signal1 = Signal(
        circuit_name="circuit_a",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
        timestamp=1.0,
    )
    listener(signal1)

    assert "circuit_a" in listener._open_threads  # type: ignore
    assert listener._open_threads["circuit_a"] == "1234.5678"  # type: ignore

    signal2 = Signal(
        circuit_name="circuit_a",
        old_state=StateEnum.OPEN,
        new_state=StateEnum.HALF_OPEN,
        timestamp=2.0,
    )
    listener(signal2)

    second_call_json = mock_client.post.call_args_list[1][1]["json"]
    assert second_call_json["thread_ts"] == "1234.5678"


@patch("httpx.Client")
def test_slack_listener_thread_cleanup(mock_client_class: MagicMock) -> None:
    """SlackListener removes thread on recovery."""
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    mock_response = Mock()
    mock_response.json.return_value = {"ok": True, "ts": "1234.5678"}
    mock_client.post.return_value = mock_response

    listener = SlackListener(channel="#test", token="xoxb-test")
    listener._open_threads["test_circuit"] = "1234.5678"  # type: ignore

    signal = Signal(
        circuit_name="test_circuit",
        old_state=StateEnum.HALF_OPEN,
        new_state=StateEnum.CLOSED,
        timestamp=1.0,
    )
    listener(signal)

    assert "test_circuit" not in listener._open_threads  # type: ignore


@patch("httpx.Client")
def test_slack_listener_error_handling(mock_client_class: MagicMock) -> None:
    """SlackListener raises error on failed API call."""
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    mock_response = Mock()
    mock_response.json.return_value = {"ok": False, "error": "channel_not_found"}
    mock_client.post.return_value = mock_response

    listener = SlackListener(channel="#invalid", token="xoxb-test")

    signal = Signal(
        circuit_name="test",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
        timestamp=1.0,
    )

    with pytest.raises(RuntimeError, match="Failed to send message"):
        listener(signal)


@patch("httpx.AsyncClient")
async def test_async_slack_listener_basic(mock_client_class: MagicMock) -> None:
    """AsyncSlackListener sends messages to Slack API."""
    mock_client = AsyncMock()
    mock_client_class.return_value = mock_client

    mock_response = Mock()
    mock_response.json.return_value = {"ok": True, "ts": "1234.5678"}
    mock_client.post.return_value = mock_response

    listener = AsyncSlackListener(channel="#alerts", token="xoxb-test")

    signal = Signal(
        circuit_name="test",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
        timestamp=1.0,
    )

    await listener(signal)

    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "https://slack.com/api/chat.postMessage"


@patch("httpx.AsyncClient")
async def test_async_slack_listener_threading(mock_client_class: MagicMock) -> None:
    """AsyncSlackListener tracks threads for related transitions."""
    mock_client = AsyncMock()
    mock_client_class.return_value = mock_client

    mock_response = Mock()
    mock_response.json.return_value = {"ok": True, "ts": "1234.5678"}
    mock_client.post.return_value = mock_response

    listener = AsyncSlackListener(channel="#test", token="xoxb-test")

    signal1 = Signal(
        circuit_name="circuit_a",
        old_state=StateEnum.CLOSED,
        new_state=StateEnum.OPEN,
        timestamp=1.0,
    )
    await listener(signal1)

    assert "circuit_a" in listener._open_threads  # type: ignore
    assert listener._open_threads["circuit_a"] == "1234.5678"  # type: ignore
