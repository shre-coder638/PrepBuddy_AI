
import json
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.test import Client
from django.utils import timezone

from reminders.models import Reminder
from notifications.models import ProcessedWhatsAppMessage
from notifications.tasks import process_due_reminders
from .test_missed_reminders import setup_data
from .test_openwa_webhook import post_event
from django.test import override_settings


@pytest.fixture(autouse=True)
def webhook_secret(settings):
    settings.OPENWA_WEBHOOK_SECRET = "test-openwa-webhook-secret"


@pytest.mark.django_db
@patch(
    "notifications.whatsapp.send_openwa_message",
    return_value={
        "messageId": "mock-message-id",
        "timestamp": 1791798618,
    },
)
def test_due_reminder_sends_through_service_and_becomes_sent(
    mock_openwa, setup_data
):
    reminder = Reminder.objects.create(
        procedure=setup_data["procedure"],
        prep_step=setup_data["critical_step"],
        scheduled_at=timezone.now() - timedelta(minutes=5),
        status="pending",
    )

    process_due_reminders()

    reminder.refresh_from_db()

    mock_openwa.assert_called_once()
    assert reminder.status == "sent"
    assert reminder.sent_at is not None
    assert reminder.delivery_attempts == 1

    payload = mock_openwa.call_args.kwargs
    assert payload["chat_id"].endswith("@c.us")
    assert "PrepBuddy Reminder" in payload["text"]


@pytest.mark.django_db
@patch(
    "notifications.whatsapp.send_openwa_message",
    side_effect=RuntimeError("Simulated OpenWA failure"),
)
def test_due_reminder_failure_is_counted_and_not_marked_sent(
    mock_openwa, setup_data
):
    reminder = Reminder.objects.create(
        procedure=setup_data["procedure"],
        prep_step=setup_data["critical_step"],
        scheduled_at=timezone.now() - timedelta(minutes=5),
        status="pending",
    )

    process_due_reminders()

    reminder.refresh_from_db()

    mock_openwa.assert_called_once()
    assert reminder.status == "pending"
    assert reminder.sent_at is None
    assert reminder.delivery_attempts == 1


@pytest.mark.django_db
@override_settings(WHATSAPP_SEND_ENABLED=False)
@patch("notifications.whatsapp.requests.post")
def test_disabled_whatsapp_does_not_mark_reminder_sent(
    mock_post, setup_data
):
    reminder = Reminder.objects.create(
        procedure=setup_data["procedure"],
        prep_step=setup_data["critical_step"],
        scheduled_at=timezone.now() - timedelta(minutes=5),
        status="pending",
    )

    process_due_reminders()

    reminder.refresh_from_db()

    # The actual sender guard must block the HTTP request.
    mock_post.assert_not_called()

    # The reminder must not be marked sent.
    assert reminder.status == "pending"
    assert reminder.sent_at is None
    assert reminder.delivery_attempts == 0


@pytest.mark.django_db
def test_scheduled_reminder_done_confirmation_and_duplicate_webhook(
    setup_data,
):
    reminder = Reminder.objects.create(
        procedure=setup_data["procedure"],
        prep_step=setup_data["critical_step"],
        scheduled_at=timezone.now() - timedelta(minutes=5),
        status="pending",
    )

    # Deliver the scheduled reminder through the outbound service.
    with patch(
        "notifications.whatsapp.send_openwa_message",
        return_value={
            "messageId": "e2e-reminder-message-123",
            "timestamp": 1791798618,
        },
    ) as reminder_sender:
        process_due_reminders()

    reminder.refresh_from_db()

    reminder_sender.assert_called_once()
    assert reminder.status == "sent"
    assert reminder.sent_at is not None
    assert reminder.openwa_message_id == "e2e-reminder-message-123"

    # Simulate the patient's WhatsApp DONE message.
    client = Client()

    with (
        patch("notifications.views.requests.get") as mock_get,
        patch("notifications.views.send_openwa_message") as ack_sender,
    ):
        mock_get.return_value = Mock(
            status_code=200,
            text='{"phone":"910000000001"}',
        )
        mock_get.return_value.json.return_value = {
            "phone": "910000000001",
        }

        inbound_event = {
            "event": "message.received",
            "data": {
                "id": "e2e-done-inbound-123",
                "from": "910000000001@c.us",
                "body": "DONE",
            },
        }

        first_response = post_event(
            client,
            inbound_event["event"],
            inbound_event["data"],
        )

        reminder.refresh_from_db()

        assert first_response.status_code == 200
        assert first_response.json()["confirmed"] is True
        assert reminder.status == "confirmed"
        assert reminder.confirmed_at is not None
        ack_sender.assert_called_once()

        # Replay the exact same inbound webhook.
        duplicate_response = post_event(
            client,
            inbound_event["event"],
            inbound_event["data"],
        )

        reminder.refresh_from_db()

        assert duplicate_response.status_code == 200
        assert duplicate_response.json()["duplicate"] is True
        assert reminder.status == "confirmed"
        ack_sender.assert_called_once()

    message_record = ProcessedWhatsAppMessage.objects.get(
        message_id="e2e-done-inbound-123",
    )
    assert message_record.is_processed is True
    assert message_record.confirmed_reminder_id == reminder.id
