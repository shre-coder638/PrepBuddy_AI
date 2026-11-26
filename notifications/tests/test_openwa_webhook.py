
import hashlib
import hmac
import json
import uuid
import pytest
from django.conf import settings
from django.test import Client, override_settings
from django.db.models.query import QuerySet
from unittest.mock import patch, Mock
from patients.models import Patient

from reminders.models import Reminder
from .test_missed_reminders import setup_data
from notifications.models import (
    ProcessedWhatsAppMessage,
    WhatsAppOutboundMessage,
    WhatsAppAssistantSession,
)

@pytest.fixture
def webhook_client():
    return Client()


@pytest.fixture(autouse=True)
def webhook_secret(settings):
    settings.OPENWA_WEBHOOK_SECRET = "test-openwa-webhook-secret"


def make_reminder(setup_data, message_id, delivery_status="accepted"):
    return Reminder.objects.create(
        procedure=setup_data["procedure"],
        prep_step=setup_data["critical_step"],
        scheduled_at=setup_data["procedure"].scheduled_at,
        status="sent",
        sent_at=None,
        openwa_message_id=message_id,
        delivery_status=delivery_status,
    )



def post_event(client, event, data, sign=True, signature=None):
    # Inbound messages require an ID for duplicate protection.
    if event == "message.received":
        data = {
            **data,
            "id": data.get("id") or data.get("messageId") or (
                f"test-inbound-{uuid.uuid4().hex}"
            ),
        }

    body = json.dumps({"event": event, "data": data}).encode("utf-8")
    headers = {}

    if sign:
        digest = hmac.new(
            settings.OPENWA_WEBHOOK_SECRET.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        headers["HTTP_X_OPENWA_SIGNATURE"] = signature or f"sha256={digest}"
    elif signature is not None:
        headers["HTTP_X_OPENWA_SIGNATURE"] = signature

    return client.post(
        "/api/notifications/openwa/webhook/",
        data=body,
        content_type="application/json",
        **headers,
    )


@pytest.mark.django_db
def test_webhook_rejects_missing_signature_before_claim(webhook_client):
    inbound_id = f"unsigned-{uuid.uuid4().hex}"

    response = post_event(
        webhook_client,
        "message.received",
        {"id": inbound_id, "from": "910000000001@c.us", "body": "DONE"},
        sign=False,
    )

    assert response.status_code == 401
    assert not ProcessedWhatsAppMessage.objects.filter(
        message_id=inbound_id,
    ).exists()


@pytest.mark.django_db
def test_webhook_rejects_invalid_signature_before_claim(webhook_client):
    inbound_id = f"invalid-signature-{uuid.uuid4().hex}"

    response = post_event(
        webhook_client,
        "message.received",
        {"id": inbound_id, "from": "910000000001@c.us", "body": "DONE"},
        signature="sha256=invalid",
    )

    assert response.status_code == 401
    assert not ProcessedWhatsAppMessage.objects.filter(
        message_id=inbound_id,
    ).exists()


def test_webhook_rejects_requests_when_secret_is_not_configured(webhook_client):
    with override_settings(OPENWA_WEBHOOK_SECRET=""):
        response = post_event(
            webhook_client,
            "message.received",
            {"id": "unconfigured-secret"},
            sign=False,
        )

    assert response.status_code == 503

@pytest.mark.django_db
@pytest.mark.parametrize(
    "sender,body",
    [
        (None, "DONE"),
        (12345, "DONE"),
        ("910000000001@c.us", None),
        ("910000000001@c.us", {"text": "DONE"}),
    ],
)
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
def test_malformed_inbound_fields_are_rejected_and_claim_released_from_processing(
    mock_get,
    mock_send,
    sender,
    body,
    webhook_client,
):
    inbound_id = f"malformed-{uuid.uuid4().hex}"

    response = post_event(
        webhook_client,
        "message.received",
        {
            "id": inbound_id,
            "from": sender,
            "body": body,
        },
    )

    message_record = ProcessedWhatsAppMessage.objects.get(
        message_id=inbound_id,
    )

    assert response.status_code == 400
    assert response.json()["processed"] is True

    assert message_record.is_processed is True
    assert message_record.processing_started_at is None

    mock_get.assert_not_called()
    mock_send.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["sent", "delivered", "read"])
def test_ack_updates_matching_reminder_delivery_status(
    webhook_client, setup_data, status
):
    reminder = make_reminder(
        setup_data,
        message_id="openwa-test-123",
    )

    response = post_event(
        webhook_client,
        "message.ack",
        {
            "messageId": "openwa-test-123",
            "status": status,
        },
    )

    reminder.refresh_from_db()

    assert response.status_code == 200
    assert response.json()["updated"] is True
    assert reminder.delivery_status == status
    assert reminder.status == "sent"


@pytest.mark.django_db
def test_failed_event_updates_matching_reminder(webhook_client, setup_data):
    reminder = make_reminder(
        setup_data,
        message_id="openwa-failed-123",
    )

    response = post_event(
        webhook_client,
        "message.failed",
        {"messageId": "openwa-failed-123"},
    )

    reminder.refresh_from_db()

    assert response.status_code == 200
    assert reminder.delivery_status == "failed"
    assert reminder.status == "sent"


@pytest.mark.django_db
def test_unknown_message_id_does_not_change_reminder(
    webhook_client, setup_data
):
    reminder = make_reminder(
        setup_data,
        message_id="openwa-known-123",
    )

    response = post_event(
        webhook_client,
        "message.ack",
        {
            "messageId": "openwa-unknown-123",
            "status": "delivered",
        },
    )

    reminder.refresh_from_db()

    assert response.status_code == 200
    assert response.json()["updated"] is False
    assert reminder.delivery_status == "accepted"


@pytest.mark.django_db
def test_missing_message_id_does_not_change_reminder(
    webhook_client, setup_data
):
    reminder = make_reminder(
        setup_data,
        message_id="openwa-known-456",
    )

    response = post_event(
        webhook_client,
        "message.ack",
        {"status": "delivered"},
    )

    reminder.refresh_from_db()

    assert response.status_code == 200
    assert response.json()["updated"] is False
    assert reminder.delivery_status == "accepted"


@pytest.mark.django_db
def test_late_failure_does_not_regress_delivered_status(
    webhook_client, setup_data
):
    reminder = make_reminder(
        setup_data,
        message_id="openwa-delivered-123",
        delivery_status="delivered",
    )

    response = post_event(
        webhook_client,
        "message.failed",
        {"messageId": "openwa-delivered-123"},
    )

    reminder.refresh_from_db()

    assert response.status_code == 200
    assert reminder.delivery_status == "delivered"


@pytest.mark.django_db
def test_delivery_ack_does_not_confirm_preparation(
    webhook_client, setup_data
):
    reminder = make_reminder(
        setup_data,
        message_id="openwa-not-confirmed-123",
    )

    response = post_event(
        webhook_client,
        "message.ack",
        {
            "messageId": "openwa-not-confirmed-123",
            "status": "delivered",
        },
    )

    reminder.refresh_from_db()

    assert response.status_code == 200
    assert reminder.delivery_status == "delivered"
    assert reminder.status == "sent"
    assert reminder.confirmed_at is None

@pytest.mark.django_db
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
def test_unregistered_sender_cannot_confirm_reminder(
    mock_get,
    mock_send,
    webhook_client,
    setup_data,
):
    reminder = make_reminder(
        setup_data,
        message_id="unregistered-test-123",
    )

    mock_get.return_value = Mock(
        status_code=200,
        text='{"phone":"919999999999"}',
    )
    mock_get.return_value.json.return_value = {
        "phone": "919999999999",
    }

    response = post_event(
        webhook_client,
        "message.received",
        {
            "from": "919999999999@c.us",
            "body": "DONE",
        },
    )

    reminder.refresh_from_db()

    assert response.status_code == 200
    assert response.json()["authorized"] is False
    assert reminder.status == "sent"
    assert reminder.confirmed_at is None
    mock_send.assert_not_called()


@pytest.mark.django_db
@patch("notifications.views.answer_question")
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
def test_unregistered_sender_cannot_access_chatbot(
    mock_get,
    mock_send,
    mock_answer,
    webhook_client,
    setup_data,
):
    mock_get.return_value = Mock(
        status_code=200,
        text='{"phone":"919999999999"}',
    )
    mock_get.return_value.json.return_value = {
        "phone": "919999999999",
    }

    response = post_event(
        webhook_client,
        "message.received",
        {
            "from": "919999999999@c.us",
            "body": "Can I drink water?",
        },
    )

    assert response.status_code == 200
    assert response.json()["authorized"] is False
    mock_answer.assert_not_called()
    mock_send.assert_not_called()


@pytest.mark.django_db
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
def test_registered_patient_can_confirm_sent_reminder(
    mock_get,
    mock_send,
    webhook_client,
    setup_data,
):
    reminder = make_reminder(
        setup_data,
        message_id="registered-test-123",
    )

    mock_get.return_value = Mock(
        status_code=200,
        text='{"phone":"910000000001"}',
    )
    mock_get.return_value.json.return_value = {
        "phone": "910000000001",
    }

    response = post_event(
        webhook_client,
        "message.received",
        {
            "from": "910000000001@c.us",
            "body": "DONE",
        },
    )

    reminder.refresh_from_db()

    assert response.status_code == 200
    assert response.json()["confirmed"] is True
    assert reminder.status == "confirmed"
    assert reminder.confirmed_at is not None
    mock_send.assert_called_once()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body, expected_confirmed",
    [
        ("done", True),
        ("  DONE  ", True),
        ("DONNE", False),
    ],
)
@patch("notifications.views.answer_question")
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
def test_done_confirmation_requires_exact_normalized_message(
    mock_get,
    mock_send,
    mock_answer,
    webhook_client,
    setup_data,
    body,
    expected_confirmed,
):
    reminder = make_reminder(
        setup_data,
        message_id=f"done-normalization-{uuid.uuid4().hex}",
    )

    mock_get.return_value = Mock(
        status_code=200,
        text='{"phone":"910000000001"}',
    )
    mock_get.return_value.json.return_value = {
        "phone": "910000000001",
    }

    response = post_event(
        webhook_client,
        "message.received",
        {
            "from": "910000000001@c.us",
            "body": body,
        },
    )

    reminder.refresh_from_db()

    assert response.status_code == 200
    assert response.json().get("confirmed", False) is expected_confirmed

    if expected_confirmed:
        assert reminder.status == "confirmed"
        assert reminder.confirmed_at is not None
        assert any(
            call.kwargs.get("purpose") == "done_ack"
            for call in mock_send.call_args_list
        )
    else:
        assert reminder.status == "sent"
        assert reminder.confirmed_at is None
        assert not any(
            call.kwargs.get("purpose") == "done_ack"
            for call in mock_send.call_args_list
        )


@patch("notifications.views.answer_question")
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
def test_registered_patient_question_uses_procedure_protocol(
    mock_get,
    mock_send,
    mock_answer,
    webhook_client,
    setup_data,
):
    procedure = setup_data["procedure"]
    patient = procedure.patient

    mock_get.return_value = Mock(
        status_code=200,
        text='{"phone":"910000000001"}',
    )
    mock_get.return_value.json.return_value = {
        "phone": "910000000001",
    }

    mock_answer.return_value = {
        "answer": "Follow your stored preparation instructions.",
        "sources": [],
        "needs_clinical_team": False,
    }

    # Activate the WhatsApp assistant session first.
    activation_response = post_event(
        webhook_client,
        "message.received",
        {
            "id": "protocol-test-activation",
            "from": "910000000001@c.us",
            "body": "TALK TO ASSISTANT",
        },
    )

    assert activation_response.status_code == 200

    # Send a separate message containing the patient's question.
    question_response = post_event(
        webhook_client,
        "message.received",
        {
            "id": "protocol-test-question",
            "from": "910000000001@c.us",
            "body": "How do I prepare for my procedure?",
        },
    )

    assert question_response.status_code == 200
    assert question_response.json()["answered"] is True

    mock_answer.assert_called_once_with(
        "How do I prepare for my procedure?",
        protocol_id=procedure.protocol_id,
        communication_style="neutral",
        requires_human=False,
    )
    mock_send.assert_called()


@pytest.mark.django_db
@patch("notifications.views.answer_question")
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
def test_patient_without_upcoming_procedure_gets_safe_fallback(
    mock_get,
    mock_send,
    mock_answer,
    webhook_client,
    setup_data,
):
    procedure = setup_data["procedure"]
    patient = procedure.patient

    # Make the patient's only procedure ineligible for preparation advice.
    procedure.status = "completed"
    procedure.save(update_fields=["status", "updated_at"])

    mock_get.return_value = Mock(
        status_code=200,
        text='{"phone":"910000000001"}',
    )
    mock_get.return_value.json.return_value = {
        "phone": "910000000001",
    }

    # Activate the assistant session.
    activation_response = post_event(
        webhook_client,
        "message.received",
        {
            "id": "fallback-test-activation",
            "from": "910000000001@c.us",
            "body": "TALK TO ASSISTANT",
        },
    )
    assert activation_response.status_code == 200

    # Ask a question when there is no eligible upcoming procedure.
    response = post_event(
        webhook_client,
        "message.received",
        {
            "id": "fallback-test-question",
            "from": "910000000001@c.us",
            "body": "How should I prepare?",
        },
    )

    assert response.status_code == 200
    assert response.json()["answered"] is True
    assert response.json()["needs_clinical_team"] is True

    mock_answer.assert_not_called()
    mock_send.assert_called()

    sent_message = mock_send.call_args.kwargs["text"]
    assert "couldn't identify an upcoming procedure" in sent_message
    assert "contact your care team" in sent_message


@pytest.mark.django_db
@patch("notifications.views.answer_question")
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
def test_followup_uses_recent_patient_question_and_same_protocol(
    mock_get,
    mock_send,
    mock_answer,
    webhook_client,
    setup_data,
):
    procedure = setup_data["procedure"]

    mock_get.return_value = Mock(
        status_code=200,
        text='{"phone":"910000000001"}',
    )
    mock_get.return_value.json.return_value = {
        "phone": "910000000001",
    }
    mock_answer.return_value = {
        "answer": "Follow your stored preparation instructions.",
        "sources": [],
        "needs_clinical_team": False,
    }

    post_event(
        webhook_client,
        "message.received",
        {
            "id": "followup-test-activation",
            "from": "910000000001@c.us",
            "body": "TALK TO ASSISTANT",
        },
    )

    post_event(
        webhook_client,
        "message.received",
        {
            "id": "followup-test-first-question",
            "from": "910000000001@c.us",
            "body": "When should I stop eating?",
        },
    )

    response = post_event(
        webhook_client,
        "message.received",
        {
            "id": "followup-test-second-question",
            "from": "910000000001@c.us",
            "body": "And when?",
        },
    )

    assert response.status_code == 200
    assert response.json()["answered"] is True

    # The follow-up includes the previous patient question as context.
    followup_call = mock_answer.call_args_list[-1]
    resolved_query = followup_call.args[0]

    assert "When should I stop eating?" in resolved_query
    assert "And when?" in resolved_query
    assert followup_call.kwargs["protocol_id"] == procedure.protocol_id


@pytest.mark.django_db
@patch("notifications.views.answer_question")
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
def test_ambiguous_followup_gets_safe_clarification(
    mock_get,
    mock_send,
    mock_answer,
    webhook_client,
    setup_data,
):
    mock_get.return_value = Mock(
        status_code=200,
        text='{"phone":"910000000001"}',
    )
    mock_get.return_value.json.return_value = {
        "phone": "910000000001",
    }
    mock_answer.return_value = {
        "answer": "Stored instruction.",
        "sources": [],
        "needs_clinical_team": False,
    }

    post_event(
        webhook_client,
        "message.received",
        {
            "id": "ambiguous-test-activation",
            "from": "910000000001@c.us",
            "body": "TALK TO ASSISTANT",
        },
    )

    post_event(
        webhook_client,
        "message.received",
        {
            "id": "ambiguous-test-first-question",
            "from": "910000000001@c.us",
            "body": "When should I stop eating?",
        },
    )

    response = post_event(
        webhook_client,
        "message.received",
        {
            "id": "ambiguous-test-second-question",
            "from": "910000000001@c.us",
            "body": "What about water?",
        },
    )

    assert response.status_code == 200
    assert response.json()["answered"] is True
    assert response.json()["needs_clinical_team"] is True

    # The ambiguous follow-up must not be passed to medical retrieval.
    assert mock_answer.call_count == 1

    sent_message = mock_send.call_args.kwargs["text"]
    assert "not sure which preparation instruction" in sent_message
    assert "clinical team" in sent_message


@pytest.mark.django_db
@patch("notifications.views.answer_question")
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
def test_unresolved_object_pronoun_requests_clarification(
    mock_get,
    mock_send,
    mock_answer,
    webhook_client,
    setup_data,
):
    mock_get.return_value = Mock(
        status_code=200,
        text='{"phone":"910000000001"}',
    )
    mock_get.return_value.json.return_value = {
        "phone": "910000000001",
    }

    post_event(
        webhook_client,
        "message.received",
        {
            "id": "object-pronoun-activation",
            "from": "910000000001@c.us",
            "body": "TALK TO ASSISTANT",
        },
    )

    response = post_event(
        webhook_client,
        "message.received",
        {
            "id": "object-pronoun-question",
            "from": "910000000001@c.us",
            "body": "Should I remove it?",
        },
    )

    assert response.status_code == 200
    assert response.json()["answered"] is True
    assert response.json()["needs_clinical_team"] is False

    mock_answer.assert_not_called()

    sent_message = mock_send.call_args.kwargs["text"]
    assert "Which item are you referring to?" in sent_message


@pytest.mark.django_db
@patch("notifications.views.answer_question")
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
def test_explicitly_named_object_proceeds_to_preparation_answer(
    mock_get,
    mock_send,
    mock_answer,
    webhook_client,
    setup_data,
):
    procedure = setup_data["procedure"]

    mock_get.return_value = Mock(
        status_code=200,
        text='{"phone":"910000000001"}',
    )
    mock_get.return_value.json.return_value = {
        "phone": "910000000001",
    }
    mock_answer.return_value = {
        "answer": "Follow the stored instructions for your procedure.",
        "sources": [],
        "needs_clinical_team": False,
    }

    post_event(
        webhook_client,
        "message.received",
        {
            "id": "named-object-activation",
            "from": "910000000001@c.us",
            "body": "TALK TO ASSISTANT",
        },
    )

    response = post_event(
        webhook_client,
        "message.received",
        {
            "id": "named-object-question",
            "from": "910000000001@c.us",
            "body": "Should I remove my earrings?",
        },
    )

    assert response.status_code == 200
    assert response.json()["answered"] is True
    assert response.json()["needs_clinical_team"] is False

    mock_answer.assert_called_once_with(
        "Should I remove my earrings?",
        protocol_id=procedure.protocol_id,
        communication_style="neutral",
        requires_human=False,
    )
    mock_send.assert_called()


@pytest.mark.django_db
@patch("notifications.views.answer_question")
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
def test_medication_safety_escalation_precedes_object_clarification(
    mock_get,
    mock_send,
    mock_answer,
    webhook_client,
    setup_data,
):
    mock_get.return_value = Mock(
        status_code=200,
        text='{"phone":"910000000001"}',
    )
    mock_get.return_value.json.return_value = {
        "phone": "910000000001",
    }

    post_event(
        webhook_client,
        "message.received",
        {
            "id": "medication-safety-activation",
            "from": "910000000001@c.us",
            "body": "TALK TO ASSISTANT",
        },
    )

    response = post_event(
        webhook_client,
        "message.received",
        {
            "id": "medication-safety-question",
            "from": "910000000001@c.us",
            "body": "Should I change my insulin dose?",
        },
    )

    assert response.status_code == 200
    assert response.json()["answered"] is True
    assert response.json()["needs_clinical_team"] is True

    mock_answer.assert_not_called()

    sent_message = mock_send.call_args.kwargs["text"]
    assert "clinical team" in sent_message.lower()

@pytest.mark.django_db
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
def test_done_acknowledgement_failure_retries_same_confirmed_reminder(
    mock_get,
    mock_send,
    webhook_client,
    setup_data,
):
    reminder = make_reminder(
        setup_data,
        message_id="done-retry-reminder-123",
    )

    # A second pending reminder must not be confirmed by the retry.
    second_reminder = make_reminder(
        setup_data,
        message_id="done-retry-reminder-456",
    )

    mock_get.return_value = Mock(
        status_code=200,
        text='{"phone":"910000000001"}',
    )
    mock_get.return_value.json.return_value = {
        "phone": "910000000001",
    }

    inbound_id = "done-ack-retry-inbound-123"

    # First acknowledgement fails; retry succeeds.
    mock_send.side_effect = [
        Exception("OpenWA unavailable"),
        None,
    ]

    inbound_data = {
        "id": inbound_id,
        "from": "910000000001@c.us",
        "body": "DONE",
    }

    first_response = post_event(
        webhook_client,
        "message.received",
        inbound_data,
    )

    reminder.refresh_from_db()
    second_reminder.refresh_from_db()

    message_record = ProcessedWhatsAppMessage.objects.get(
        message_id=inbound_id,
    )

    assert first_response.status_code == 500
    assert first_response.json()["confirmed"] is True
    assert first_response.json()["acknowledgement_sent"] is False

    assert reminder.status == "confirmed"
    assert reminder.confirmed_at is not None
    assert message_record.confirmed_reminder_id == reminder.id
    assert message_record.is_processed is False
    assert message_record.processing_started_at is None

    assert second_reminder.status == "sent"
    assert second_reminder.confirmed_at is None

    # Retry the exact same inbound WhatsApp message.
    second_response = post_event(
        webhook_client,
        "message.received",
        inbound_data,
    )

    reminder.refresh_from_db()
    second_reminder.refresh_from_db()
    message_record.refresh_from_db()

    assert second_response.status_code == 200
    assert second_response.json()["confirmed"] is True
    assert second_response.json()["reminder_id"] == reminder.id
    assert second_response.json()["acknowledgement_sent"] is True

    assert reminder.status == "confirmed"
    assert second_reminder.status == "sent"
    assert message_record.confirmed_reminder_id == reminder.id
    assert message_record.is_processed is True
    assert message_record.processing_started_at is None

    assert mock_send.call_count == 2

def make_outbound(message_id, purpose="assistant_answer"):
    return WhatsAppOutboundMessage.objects.create(
        purpose=purpose,
        dedupe_key=f"test:{uuid.uuid4().hex}",
        openwa_session_id="test-session",
        chat_id="910000000001@c.us",
        message_text="Test message",
        payload_sha256="a" * 64,
        status="accepted",
        openwa_message_id=message_id,
    )


@pytest.mark.django_db
def test_ack_updates_outbound_delivery_status(webhook_client):
    outbound = make_outbound("outbox-ack-123")

    response = post_event(
        webhook_client,
        "message.ack",
        {
            "messageId": "outbox-ack-123",
            "status": "delivered",
        },
    )

    outbound.refresh_from_db()

    assert response.status_code == 200
    assert response.json()["updated"] is True
    assert outbound.status == "accepted"
    assert outbound.delivery_status == "delivered"


@pytest.mark.django_db
def test_non_reminder_ack_updates_outbound_ledger(webhook_client):
    outbound = make_outbound(
        "outbox-assistant-123",
        purpose="assistant_answer",
    )

    response = post_event(
        webhook_client,
        "message.ack",
        {
            "messageId": "outbox-assistant-123",
            "status": "read",
        },
    )

    outbound.refresh_from_db()

    assert response.status_code == 200
    assert response.json()["updated"] is True
    assert outbound.delivery_status == "read"


@pytest.mark.django_db
def test_ambiguous_outbound_message_id_is_not_updated(webhook_client):
    first = make_outbound("duplicate-outbox-id")
    second = make_outbound("duplicate-outbox-id")

    response = post_event(
        webhook_client,
        "message.ack",
        {
            "messageId": "duplicate-outbox-id",
            "status": "delivered",
        },
    )

    first.refresh_from_db()
    second.refresh_from_db()

    assert response.status_code == 200
    assert first.delivery_status == "pending"
    assert second.delivery_status == "pending"


@pytest.mark.django_db
def test_unexpected_webhook_exception_releases_inbound_claim(webhook_client):
    inbound_id = f"unexpected-{uuid.uuid4().hex}"
    inbound_data = {
        "id": inbound_id,
        "from": None,
        "body": "DONE",
    }

    # Force an unexpected exception after the inbound message is claimed.
    with patch(
        "notifications.views.mark_whatsapp_message_processed",
        side_effect=RuntimeError("Simulated processing failure"),
    ):
        response = post_event(
            webhook_client,
            "message.received",
            inbound_data,
        )

    message_record = ProcessedWhatsAppMessage.objects.get(
        message_id=inbound_id,
    )

    assert response.status_code == 500
    assert message_record.is_processed is False
    assert message_record.processing_started_at is None

    # The same message can now be claimed and safely handled again.
    retry_response = post_event(
        webhook_client,
        "message.received",
        inbound_data,
    )

    message_record.refresh_from_db()

    assert retry_response.status_code == 400
    assert message_record.is_processed is True
    assert message_record.processing_started_at is None


@pytest.mark.django_db
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
def test_registered_patient_activation_is_idempotent(
    mock_get,
    mock_send,
    webhook_client,
    setup_data,
):
    patient = setup_data["procedure"].patient

    mock_get.return_value = Mock(
        status_code=200,
        text='{"phone":"910000000001"}',
    )
    mock_get.return_value.json.return_value = {
        "phone": "910000000001",
    }

    event = {
        "id": "dedicated-activation-test",
        "from": "910000000001@c.us",
        "body": "TALK TO ASSISTANT",
    }

    first_response = post_event(
        webhook_client,
        "message.received",
        event,
    )

    assert first_response.status_code == 200
    assert first_response.json()["assistant_activated"] is True

    session = WhatsAppAssistantSession.objects.get(patient=patient)
    assert session.is_active is True
    assert session.activated_at is not None

    message_record = ProcessedWhatsAppMessage.objects.get(
        message_id=event["id"],
    )
    assert message_record.is_processed is True

    mock_send.assert_called_once()
    assert (
        mock_send.call_args.kwargs["purpose"]
        == "assistant_activation"
    )

    duplicate_response = post_event(
        webhook_client,
        "message.received",
        event,
    )

    assert duplicate_response.status_code == 200
    assert duplicate_response.json()["duplicate"] is True

    mock_send.assert_called_once()
    assert WhatsAppAssistantSession.objects.filter(
        patient=patient,
    ).count() == 1
from datetime import timedelta
from django.utils import timezone


@pytest.mark.django_db
def test_stale_worker_cannot_mark_reclaimed_message_processed():
    from notifications.views import mark_whatsapp_message_processed

    original_claim = timezone.now()
    newer_claim = original_claim + timedelta(seconds=1)

    record = ProcessedWhatsAppMessage.objects.create(
        message_id="stale-completion-test",
        processing_started_at=original_claim,
    )

    ProcessedWhatsAppMessage.objects.filter(pk=record.pk).update(
        processing_started_at=newer_claim,
    )

    assert mark_whatsapp_message_processed(record) is False

    record.refresh_from_db()
    assert record.is_processed is False
    assert record.processed_at is None
    assert record.processing_started_at == newer_claim


@pytest.mark.django_db
def test_stale_worker_cannot_release_reclaimed_message():
    from notifications.views import release_whatsapp_message_claim

    original_claim = timezone.now()
    newer_claim = original_claim + timedelta(seconds=1)

    record = ProcessedWhatsAppMessage.objects.create(
        message_id="stale-release-test",
        processing_started_at=original_claim,
    )

    ProcessedWhatsAppMessage.objects.filter(pk=record.pk).update(
        processing_started_at=newer_claim,
    )

    assert release_whatsapp_message_claim(record) is False

    record.refresh_from_db()
    assert record.is_processed is False
    assert record.processing_started_at == newer_claim



@pytest.mark.django_db
def test_new_inbound_message_can_be_claimed():
    import uuid
    from notifications.models import ProcessedWhatsAppMessage
    from notifications.views import claim_whatsapp_message

    message_id = f"claim-new-{uuid.uuid4().hex}"

    record, claimed = claim_whatsapp_message(message_id)

    assert claimed is True
    assert record.message_id == message_id
    assert record.is_processed is False
    assert record.processing_started_at is not None


@pytest.mark.django_db
def test_active_inbound_claim_cannot_be_reclaimed():
    import uuid
    from django.utils import timezone
    from notifications.models import ProcessedWhatsAppMessage
    from notifications.views import claim_whatsapp_message

    message_id = f"claim-active-{uuid.uuid4().hex}"
    original_claim = timezone.now()

    record = ProcessedWhatsAppMessage.objects.create(
        message_id=message_id,
        processing_started_at=original_claim,
    )

    returned_record, claimed = claim_whatsapp_message(message_id)

    assert claimed is False
    assert returned_record.pk == record.pk
    record.refresh_from_db()
    assert record.processing_started_at == original_claim


@pytest.mark.django_db
def test_expired_inbound_claim_can_be_reclaimed():
    import uuid
    from datetime import timedelta
    from django.utils import timezone
    from notifications.models import ProcessedWhatsAppMessage
    from notifications.views import claim_whatsapp_message

    message_id = f"claim-expired-{uuid.uuid4().hex}"
    original_claim = timezone.now() - timedelta(minutes=6)

    record = ProcessedWhatsAppMessage.objects.create(
        message_id=message_id,
        processing_started_at=original_claim,
    )

    returned_record, claimed = claim_whatsapp_message(message_id)

    assert claimed is True
    assert returned_record.pk == record.pk
    record.refresh_from_db()
    assert record.processing_started_at > original_claim


@pytest.mark.django_db
def test_processed_inbound_message_cannot_be_claimed_again():
    import uuid
    from django.utils import timezone
    from notifications.models import ProcessedWhatsAppMessage
    from notifications.views import claim_whatsapp_message

    message_id = f"claim-processed-{uuid.uuid4().hex}"

    record = ProcessedWhatsAppMessage.objects.create(
        message_id=message_id,
        is_processed=True,
        processed_at=timezone.now(),
    )

    returned_record, claimed = claim_whatsapp_message(message_id)

    assert claimed is False
    assert returned_record.pk == record.pk
    record.refresh_from_db()
    assert record.is_processed is True
    assert record.processing_started_at is None

@pytest.mark.django_db
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
def test_missed_transition_wins_race_with_done_confirmation(
    mock_get,
    mock_send,
    webhook_client,
    setup_data,
):
    reminder = make_reminder(
        setup_data,
        message_id=f"missed-race-{uuid.uuid4().hex}",
    )
    inbound_id = f"done-after-missed-{uuid.uuid4().hex}"

    mock_get.return_value = Mock(
        status_code=200,
        text='{"phone":"910000000001"}',
    )
    mock_get.return_value.json.return_value = {
        "phone": "910000000001",
    }

    original_update = QuerySet.update
    competing_missed_transition_applied = False

    def apply_competing_missed_transition(queryset, **kwargs):
        nonlocal competing_missed_transition_applied

        if kwargs.get("status") == "confirmed" and not competing_missed_transition_applied:
            competing_missed_transition_applied = True
            original_update(
                Reminder.objects.filter(pk=reminder.pk),
                status="missed",
            )

        return original_update(queryset, **kwargs)

    with patch.object(QuerySet, "update", new=apply_competing_missed_transition):
        response = post_event(
            webhook_client,
            "message.received",
            {
                "id": inbound_id,
                "from": "910000000001@c.us",
                "body": "DONE",
            },
        )

    reminder.refresh_from_db()
    message_record = ProcessedWhatsAppMessage.objects.get(
        message_id=inbound_id,
    )

    assert response.status_code == 200
    assert response.json()["confirmed"] is False
    assert response.json()["message"] == "No pending reminder found"
    assert competing_missed_transition_applied is True
    assert reminder.status == "missed"
    assert reminder.confirmed_at is None
    assert message_record.confirmed_reminder_id is None
    assert message_record.is_processed is True
    mock_send.assert_not_called()


@pytest.mark.django_db
@patch("notifications.views.answer_question")
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
def test_ambiguous_assistant_send_does_not_send_second_reply(
    mock_get,
    mock_send,
    mock_answer,
    webhook_client,
    setup_data,
):
    from notifications.whatsapp import WhatsAppOutboundError

    mock_get.return_value = Mock(status_code=200)
    mock_get.return_value.json.return_value = {
        "phone": "910000000001",
    }

    mock_answer.return_value = {
        "answer": "Read the synthetic preparation notice.",
        "sources": [],
        "needs_clinical_team": False,
    }

    activation = post_event(
        webhook_client,
        "message.received",
        {
            "id": "ambiguous-send-activation",
            "from": "910000000001@c.us",
            "body": "TALK TO ASSISTANT",
        },
    )

    assert activation.status_code == 200

    mock_send.reset_mock()

    mock_send.side_effect = WhatsAppOutboundError(
        "OpenWA returned an ambiguous HTTP status (502)."
    )

    event = {
        "id": "ambiguous-send-question",
        "from": "910000000001@c.us",
        "body": "How do I prepare for my procedure?",
    }

    response = post_event(
        webhook_client,
        "message.received",
        event,
    )

    assert response.status_code == 503
    assert response.json()["delivery_uncertain"] is True
    assert response.json()["fallback"] is False

    # No second outbound message may be attempted.
    assert mock_send.call_count == 1

    original_key = mock_send.call_args.kwargs["dedupe_key"]

    assert original_key == (
        "inbound:ambiguous-send-question:assistant_answer"
    )

    record = ProcessedWhatsAppMessage.objects.get(
        message_id=event["id"]
    )

    assert record.is_processed is False
    assert record.processing_started_at is None

    # A webhook retry must reuse the original outbound key.
    mock_send.reset_mock()
    mock_send.side_effect = None
    mock_send.return_value = {
        "success": True,
        "messageId": "synthetic-accepted-message",
    }

    retry = post_event(
        webhook_client,
        "message.received",
        event,
    )

    assert retry.status_code == 200
    assert retry.json()["answered"] is True
    assert mock_send.call_count == 1

    assert (
        mock_send.call_args.kwargs["dedupe_key"]
        == original_key
    )

    record.refresh_from_db()
    assert record.is_processed is True
