
import json

import pytest
from django.test import Client

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
