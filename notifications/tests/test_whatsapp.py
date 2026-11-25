from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
import requests
from django.test import override_settings
from django.utils import timezone

from notifications.models import WhatsAppOutboundMessage
from notifications.whatsapp import (
    WhatsAppOutboundError,
    WhatsAppIdempotencyExpired,
    WhatsAppPayloadConflict,
    WhatsAppSendInProgress,
    send_openwa_message,
    send_whatsapp_template,
)


BASE_SETTINGS = {
    "OPENWA_BASE_URL": "http://localhost:2785",
    "OPENWA_SESSION_ID": "test-session",
    "OPENWA_API_KEY": "test-api-key",
    "WHATSAPP_SEND_ENABLED": True,
}


def successful_response(message_id="test-message-id"):
    response = Mock()
    response.status_code = 201
    response.json.return_value = {
        "success": True,
        "messageId": message_id,
        "timestamp": 1791798618,
    }
    return response


def send_test_message(text="Test message", dedupe_key="test:1", **kwargs):
    return send_openwa_message(
        chat_id=kwargs.get("chat_id", "917970412321@c.us"),
        text=text,
        dedupe_key=dedupe_key,
        purpose=kwargs.get("purpose", "test_message"),
    )


@pytest.mark.django_db
@override_settings(
    **BASE_SETTINGS,
    OPENWA_RELAY_URL="",
    OPENWA_PROXY_TOKEN="",
)
@patch("notifications.whatsapp.requests.post")
def test_send_openwa_message_success(mock_post):
    mock_post.return_value = successful_response()

    result = send_test_message()

    outbound = WhatsAppOutboundMessage.objects.get(dedupe_key="test:1")

    assert result["messageId"] == "test-message-id"
    assert result["outbox_id"] == str(outbound.pk)
    assert outbound.status == "accepted"
    assert outbound.attempts == 1
    assert outbound.openwa_message_id == "test-message-id"
    assert outbound.accepted_at is not None

    mock_post.assert_called_once_with(
        "http://localhost:2785/api/sessions/test-session/messages/send-text",
        headers={
            "X-API-Key": "test-api-key",
            "Content-Type": "application/json",
            "Idempotency-Key": str(outbound.pk),
        },
        json={
            "chatId": "917970412321@c.us",
            "text": "Test message",
        },
        timeout=15,
    )


@pytest.mark.django_db
@override_settings(**BASE_SETTINGS)
@patch("notifications.whatsapp.requests.post")
def test_accepted_message_is_not_sent_twice(mock_post):
    mock_post.return_value = successful_response()

    first = send_test_message()
    second = send_test_message()

    assert first["outbox_id"] == second["outbox_id"]
    assert second["replayed"] is True
    assert second["messageId"] == "test-message-id"
    mock_post.assert_called_once()


@pytest.mark.django_db
@override_settings(**BASE_SETTINGS)
@patch("notifications.whatsapp.requests.post")
def test_retry_reuses_original_persisted_payload(mock_post):
    mock_post.side_effect = [
        requests.Timeout("Connection timed out"),
        successful_response(),
    ]

    with pytest.raises(WhatsAppOutboundError):
        send_test_message(text="Original message")

    outbound = WhatsAppOutboundMessage.objects.get(dedupe_key="test:1")

    # An ambiguous send must not be retried during the active lease.
    with pytest.raises(WhatsAppSendInProgress):
        send_test_message(text="Regenerated message")

    mock_post.assert_called_once()

    # Simulate the lease expiring so a safe retry can proceed.
    WhatsAppOutboundMessage.objects.filter(pk=outbound.pk).update(
        lease_until=timezone.now() - timedelta(seconds=1)
    )

    result = send_test_message(text="Regenerated message")

    outbound.refresh_from_db()

    assert result["messageId"] == "test-message-id"
    assert outbound.message_text == "Original message"
    assert outbound.status == "accepted"
    assert outbound.attempts == 2

    first_call = mock_post.call_args_list[0]
    second_call = mock_post.call_args_list[1]

    assert first_call.kwargs["json"]["text"] == "Original message"
    assert second_call.kwargs["json"]["text"] == "Original message"
    assert (
        first_call.kwargs["headers"]["Idempotency-Key"]
        == second_call.kwargs["headers"]["Idempotency-Key"]
    )


@pytest.mark.django_db
@override_settings(**BASE_SETTINGS)
@patch("notifications.whatsapp.requests.post")
@pytest.mark.parametrize(
    "changed_kwargs",
    [
        {"chat_id": "919999999999@c.us"},
        {"purpose": "different_purpose"},
    ],
)
def test_dedupe_key_rejects_different_send(
    mock_post,
    changed_kwargs,
):
    mock_post.return_value = successful_response()

    send_test_message()

    with pytest.raises(WhatsAppPayloadConflict):
        send_test_message(**changed_kwargs)

    mock_post.assert_called_once()


@pytest.mark.django_db
@override_settings(**BASE_SETTINGS)
@patch("notifications.whatsapp.requests.post")
def test_network_error_records_unknown_status(mock_post):
    mock_post.side_effect = requests.ConnectionError("Connection lost")

    with pytest.raises(WhatsAppOutboundError, match="outcome is unknown"):
        send_test_message()

    outbound = WhatsAppOutboundMessage.objects.get(dedupe_key="test:1")

    assert outbound.status == "unknown"
    assert outbound.lease_until is not None
    assert outbound.lease_until > timezone.now()
    assert outbound.attempts == 1


@pytest.mark.django_db
@override_settings(**BASE_SETTINGS)
@patch("notifications.whatsapp.requests.post")
@pytest.mark.parametrize("status_code", [409, 500, 502, 503])
def test_ambiguous_http_status_records_unknown(mock_post, status_code):
    response = Mock()
    response.status_code = status_code
    mock_post.return_value = response

    with pytest.raises(WhatsAppOutboundError):
        send_test_message()

    outbound = WhatsAppOutboundMessage.objects.get(dedupe_key="test:1")

    assert outbound.status == "unknown"
    assert outbound.lease_until is not None
    assert outbound.lease_until > timezone.now()


@pytest.mark.django_db
@override_settings(**BASE_SETTINGS)
@patch("notifications.whatsapp.requests.post")
def test_http_client_error_records_failed(mock_post):
    response = Mock()
    response.status_code = 400
    response.raise_for_status.side_effect = requests.HTTPError(
        "400 Bad Request"
    )
    mock_post.return_value = response

    with pytest.raises(requests.HTTPError):
        send_test_message()

    outbound = WhatsAppOutboundMessage.objects.get(dedupe_key="test:1")

    assert outbound.status == "failed"
    assert outbound.lease_until is None


@pytest.mark.django_db
@override_settings(**BASE_SETTINGS)
@patch("notifications.whatsapp.requests.post")
def test_expired_idempotency_window_blocks_retry(mock_post):
    outbound = WhatsAppOutboundMessage.objects.create(
        purpose="test_message",
        dedupe_key="test:expired",
        openwa_session_id="test-session",
        chat_id="917970412321@c.us",
        message_text="Test message",
        payload_sha256=(
            "e3b0c44298fc1c149afbf4c8996fb924"
            "27ae41e4649b934ca495991b7852b855"
        ),
        status="unknown",
        first_attempt_at=(
            timezone.now() - timedelta(hours=24)
        ),
    )

    # Store a valid digest for the persisted payload.
    import hashlib
    import json

    canonical = json.dumps(
        {
            "session_id": "test-session",
            "chat_id": "917970412321@c.us",
            "text": "Test message",
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    outbound.payload_sha256 = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    outbound.save(update_fields=["payload_sha256"])

    with pytest.raises(WhatsAppIdempotencyExpired):
        send_test_message(dedupe_key="test:expired")

    outbound.refresh_from_db()
    assert outbound.status == "expired"
    mock_post.assert_not_called()


@pytest.mark.django_db
@override_settings(**BASE_SETTINGS)
@patch("notifications.whatsapp.requests.post")
def test_active_lease_prevents_second_send(mock_post):
    outbound = WhatsAppOutboundMessage.objects.create(
        purpose="test_message",
        dedupe_key="test:leased",
        openwa_session_id="test-session",
        chat_id="917970412321@c.us",
        message_text="Test message",
        payload_sha256="",
        status="sending",
        lease_until=timezone.now() + timedelta(seconds=30),
    )

    import hashlib
    import json

    canonical = json.dumps(
        {
            "session_id": "test-session",
            "chat_id": "917970412321@c.us",
            "text": "Test message",
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    outbound.payload_sha256 = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    outbound.save(update_fields=["payload_sha256"])

    with pytest.raises(WhatsAppSendInProgress):
        send_test_message(dedupe_key="test:leased")

    mock_post.assert_not_called()


@pytest.mark.django_db
@override_settings(**BASE_SETTINGS)
@patch("notifications.whatsapp.send_openwa_message")
def test_template_formats_recipient_and_message(mock_send):
    mock_send.return_value = {
        "success": True,
        "messageId": "test-message-id",
    }

    result = send_whatsapp_template(
        phone_number="+917970412321",
        patient_name="Rahul",
        procedure_name="Test Procedure",
        preparation_step="Stop eating solid foods",
        instructions="Follow the instructions provided by your care team.",
        dedupe_key="reminder:1:standard",
        purpose="standard_reminder",
    )

    assert result["messageId"] == "test-message-id"

    kwargs = mock_send.call_args.kwargs
    assert kwargs["chat_id"] == "917970412321@c.us"
    assert kwargs["dedupe_key"] == "reminder:1:standard"
    assert kwargs["purpose"] == "standard_reminder"
    assert "Rahul" in kwargs["text"]
    assert "Test Procedure" in kwargs["text"]
    assert "Stop eating solid foods" in kwargs["text"]


@pytest.mark.django_db
@override_settings(**BASE_SETTINGS)
@patch("notifications.whatsapp.send_openwa_message")
@pytest.mark.parametrize(
    "bad_result",
    [None, "unexpected response", []],
)
def test_template_rejects_unexpected_response(mock_send, bad_result):
    mock_send.return_value = bad_result

    with pytest.raises(RuntimeError, match="unexpected response format"):
        send_whatsapp_template(
            phone_number="+917970412321",
            patient_name="Rahul",
            procedure_name="Test Procedure",
            preparation_step="Test step",
            instructions="Test instructions",
            dedupe_key="reminder:1:test",
            purpose="test_reminder",
        )


@pytest.mark.django_db
@override_settings(**BASE_SETTINGS)
@patch("notifications.whatsapp.send_openwa_message")
@pytest.mark.parametrize(
    "failure_result",
    [{"success": False}, {"sent": False}],
)
def test_template_rejects_explicit_failure(mock_send, failure_result):
    mock_send.return_value = failure_result

    with pytest.raises(RuntimeError, match="delivery failure"):
        send_whatsapp_template(
            phone_number="+917970412321",
            patient_name="Rahul",
            procedure_name="Test Procedure",
            preparation_step="Test step",
            instructions="Test instructions",
            dedupe_key="reminder:1:test",
            purpose="test_reminder",
        )


@pytest.mark.django_db
@override_settings(WHATSAPP_SEND_ENABLED=False)
@patch("notifications.whatsapp.requests.post")
def test_disabled_whatsapp_sending_never_calls_openwa(mock_post):
    with pytest.raises(
        RuntimeError,
        match="WhatsApp sending is disabled by configuration",
    ):
        send_test_message()

    mock_post.assert_not_called()
    assert WhatsAppOutboundMessage.objects.count() == 0
from django.utils import timezone


@pytest.mark.django_db
@override_settings(**BASE_SETTINGS)
@patch("notifications.whatsapp.requests.post")
def test_late_network_error_cannot_overwrite_accepted_status(mock_post):
    def late_network_error(*args, **kwargs):
        outbound = WhatsAppOutboundMessage.objects.get(dedupe_key="test:1")
        WhatsAppOutboundMessage.objects.filter(pk=outbound.pk).update(
            status="accepted",
            lease_until=None,
            accepted_at=timezone.now(),
            openwa_message_id="winner-message",
        )
        raise requests.Timeout("Late timeout")

    mock_post.side_effect = late_network_error

    with pytest.raises(WhatsAppOutboundError, match="outcome is unknown"):
        send_test_message()

    outbound = WhatsAppOutboundMessage.objects.get(dedupe_key="test:1")
    assert outbound.status == "accepted"
    assert outbound.openwa_message_id == "winner-message"


@pytest.mark.django_db
@override_settings(**BASE_SETTINGS)
@patch("notifications.whatsapp.requests.post")
def test_late_success_does_not_replace_other_workers_accepted_message(mock_post):
    def late_success(*args, **kwargs):
        outbound = WhatsAppOutboundMessage.objects.get(dedupe_key="test:1")
        WhatsAppOutboundMessage.objects.filter(pk=outbound.pk).update(
            status="accepted",
            lease_until=None,
            accepted_at=timezone.now(),
            openwa_message_id="winner-message",
        )
        return successful_response("late-worker-message")

    mock_post.side_effect = late_success

    result = send_test_message()

    outbound = WhatsAppOutboundMessage.objects.get(dedupe_key="test:1")
    assert outbound.status == "accepted"
    assert outbound.openwa_message_id == "winner-message"
    assert result["messageId"] == "winner-message"
    assert result["replayed"] is True


@pytest.mark.django_db
@override_settings(**BASE_SETTINGS)
@patch("notifications.whatsapp.requests.post")
def test_late_http_failure_cannot_overwrite_accepted_status(mock_post):
    def late_http_failure(*args, **kwargs):
        outbound = WhatsAppOutboundMessage.objects.get(dedupe_key="test:1")
        WhatsAppOutboundMessage.objects.filter(pk=outbound.pk).update(
            status="accepted",
            lease_until=None,
            accepted_at=timezone.now(),
            openwa_message_id="winner-message",
        )

        response = Mock()
        response.status_code = 400
        response.raise_for_status.side_effect = requests.HTTPError(
            "Late HTTP error"
        )
        return response

    mock_post.side_effect = late_http_failure

    with pytest.raises(requests.HTTPError, match="Late HTTP error"):
        send_test_message()

    outbound = WhatsAppOutboundMessage.objects.get(dedupe_key="test:1")
    assert outbound.status == "accepted"
    assert outbound.openwa_message_id == "winner-message"


@pytest.mark.django_db
@override_settings(
    **BASE_SETTINGS,
    OPENWA_RELAY_URL="https://example.ngrok-free.dev/api/notifications/openwa/relay/send-text/",
    OPENWA_PROXY_TOKEN="test-proxy-token",
)
@patch("notifications.whatsapp.requests.post")
def test_send_openwa_message_uses_configured_relay(mock_post):
    mock_post.return_value = successful_response()

    result = send_test_message()

    outbound = WhatsAppOutboundMessage.objects.get(dedupe_key="test:1")

    assert result["messageId"] == "test-message-id"
    assert outbound.status == "accepted"

    mock_post.assert_called_once_with(
        "https://example.ngrok-free.dev/api/notifications/openwa/relay/send-text/",
        headers={
            "X-Proxy-Token": "test-proxy-token",
            "Content-Type": "application/json",
            "Idempotency-Key": str(outbound.pk),
        },
        json={
            "chatId": "917970412321@c.us",
            "text": "Test message",
        },
        timeout=15,
    )

    sent_headers = mock_post.call_args.kwargs["headers"]
    assert "X-API-Key" not in sent_headers


@pytest.mark.django_db
@override_settings(
    **BASE_SETTINGS,
    OPENWA_RELAY_URL="https://example.ngrok-free.dev/api/notifications/openwa/relay/send-text/",
    OPENWA_PROXY_TOKEN="",
)
@patch("notifications.whatsapp.requests.post")
def test_relay_send_fails_safely_without_proxy_token(mock_post):
    with pytest.raises(
        WhatsAppOutboundError,
        match="relay authentication is not configured",
    ):
        send_test_message()

    outbound = WhatsAppOutboundMessage.objects.get(dedupe_key="test:1")

    assert outbound.status == "failed"
    mock_post.assert_not_called()
