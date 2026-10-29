
import json
import uuid
import pytest
from django.test import Client
from unittest.mock import patch, Mock
from patients.models import Patient

from reminders.models import Reminder
from .test_missed_reminders import setup_data


@pytest.fixture
def webhook_client():
    return Client()


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



def post_event(client, event, data):
    # Inbound messages require an ID for duplicate protection.
    if event == "message.received":
        data = {
            **data,
            "id": data.get("id") or data.get("messageId") or (
                f"test-inbound-{uuid.uuid4().hex}"
            ),
        }

    return client.post(
        "/api/notifications/openwa/webhook/",
        data=json.dumps({"event": event, "data": data}),
        content_type="application/json",
    )



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

    sent_message = mock_send.call_args.args[1]
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

    sent_message = mock_send.call_args.args[1]
    assert "not sure which preparation instruction" in sent_message
    assert "clinical team" in sent_message
