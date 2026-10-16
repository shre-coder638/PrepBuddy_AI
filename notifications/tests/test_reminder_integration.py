
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from reminders.models import Reminder
from notifications.tasks import process_due_reminders
from .test_missed_reminders import setup_data
from django.test import override_settings


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
    assert reminder.delivery_attempts == 1
