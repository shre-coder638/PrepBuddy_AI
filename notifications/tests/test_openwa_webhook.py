
import json

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