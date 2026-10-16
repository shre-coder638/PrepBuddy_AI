
import json
from unittest.mock import Mock, patch

import pytest
import requests
from django.test import override_settings

from notifications.whatsapp import (
    send_openwa_message,
    send_whatsapp_template,
)


@override_settings(
    OPENWA_BASE_URL="http://localhost:2785",
    OPENWA_SESSION_ID="test-session",
    OPENWA_API_KEY="test-api-key",
    WHATSAPP_SEND_ENABLED=True,
)
@patch("notifications.whatsapp.requests.post")
def test_send_openwa_message_success(mock_post):
    response = Mock()
    response.status_code = 201
    response.text = '{"messageId": "test-message-id"}'
    response.json.return_value = {
        "messageId": "test-message-id",
        "timestamp": 1791798618,
    }
    mock_post.return_value = response

    result = send_openwa_message(
        chat_id="917970412321@c.us",
        text="Test message",
    )

    assert result["messageId"] == "test-message-id"
    mock_post.assert_called_once_with(
        "http://localhost:2785/api/sessions/test-session/messages/send-text",
        headers={
            "X-API-Key": "test-api-key",
            "Content-Type": "application/json",
        },
        json={
            "chatId": "917970412321@c.us",
            "text": "Test message",
        },
        timeout=15,
    )


@override_settings(
    OPENWA_BASE_URL="http://localhost:2785",
    OPENWA_SESSION_ID="test-session",
    OPENWA_API_KEY="test-api-key",
    WHATSAPP_SEND_ENABLED=True,
)
@patch("notifications.whatsapp.requests.post")
def test_send_openwa_message_http_error_raises(mock_post):
    response = Mock()
    response.status_code = 500
    response.text = '{"message": "Internal server error"}'
    response.raise_for_status.side_effect = requests.HTTPError(
        "500 Server Error"
    )
    mock_post.return_value = response

    with pytest.raises(requests.HTTPError):
        send_openwa_message(
            chat_id="917970412321@c.us",
            text="Test message",
        )


@patch("notifications.whatsapp.send_openwa_message")
def test_template_formats_recipient_and_message(mock_send):
    mock_send.return_value = {
        "messageId": "test-message-id",
        "timestamp": 1791798618,
    }

    result = send_whatsapp_template(
        phone_number="+917970412321",
        patient_name="Rahul",
        procedure_name="Test Procedure",
        preparation_step="Stop eating solid foods",
        instructions="Follow the instructions provided by your care team.",
    )

    assert result["messageId"] == "test-message-id"

    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["chat_id"] == "917970412321@c.us"
    assert "Rahul" in kwargs["text"]
    assert "Test Procedure" in kwargs["text"]
    assert "Stop eating solid foods" in kwargs["text"]


@pytest.mark.parametrize(
    "bad_result",
    [
        None,
        "unexpected response",
        [],
    ],
)
@patch("notifications.whatsapp.send_openwa_message")
def test_template_rejects_unexpected_response(mock_send, bad_result):
    mock_send.return_value = bad_result

    with pytest.raises(RuntimeError, match="unexpected response format"):
        send_whatsapp_template(
            phone_number="+917970412321",
            patient_name="Rahul",
            procedure_name="Test Procedure",
            preparation_step="Test step",
            instructions="Test instructions",
        )


@pytest.mark.parametrize(
    "failure_result",
    [
        {"success": False},
        {"sent": False},
    ],
)
@patch("notifications.whatsapp.send_openwa_message")
def test_template_rejects_explicit_failure(mock_send, failure_result):
    mock_send.return_value = failure_result

    with pytest.raises(RuntimeError, match="delivery failure"):
        send_whatsapp_template(
            phone_number="+917970412321",
            patient_name="Rahul",
            procedure_name="Test Procedure",
            preparation_step="Test step",
            instructions="Test instructions",
        )


@override_settings(WHATSAPP_SEND_ENABLED=False)
@patch("notifications.whatsapp.requests.post")
def test_disabled_whatsapp_sending_never_calls_openwa(mock_post):
    with pytest.raises(
        RuntimeError,
        match="WhatsApp sending is disabled by configuration",
    ):
        send_openwa_message(
            chat_id="917970412321@c.us",
            text="This must not be sent",
        )

    mock_post.assert_not_called()
