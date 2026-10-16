
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from reminders.models import Reminder
from notifications.tasks import process_due_reminders

from .test_missed_reminders import setup_data


@pytest.mark.django_db
@patch(
    "notifications.tasks.send_reminder",
    return_value={"messageId": "mock-message-id", "timestamp": 1234567890},
)
def test_due_pending_reminder_becomes_sent(mock_send, setup_data):
    procedure = setup_data["procedure"]

    reminder = Reminder.objects.create(
        procedure=procedure,
        prep_step=setup_data["critical_step"],
        scheduled_at=timezone.now() - timedelta(minutes=5),
        status="pending",
    )

    process_due_reminders()

    reminder.refresh_from_db()

    mock_send.assert_called_once()
    assert reminder.status == "sent"
    assert reminder.sent_at is not None


@pytest.mark.django_db
@patch("notifications.tasks.send_reminder", return_value=True)
def test_future_reminder_remains_pending(mock_send, setup_data):
    procedure = setup_data["procedure"]

    reminder = Reminder.objects.create(
        procedure=procedure,
        prep_step=setup_data["critical_step"],
        scheduled_at=timezone.now() + timedelta(hours=2),
        status="pending",
    )

    process_due_reminders()

    reminder.refresh_from_db()

    mock_send.assert_not_called()
    assert reminder.status == "pending"
    assert reminder.sent_at is None


@pytest.mark.django_db
@patch("notifications.tasks.send_reminder", return_value=False)
def test_failed_send_does_not_mark_reminder_sent(mock_send, setup_data):
    procedure = setup_data["procedure"]

    reminder = Reminder.objects.create(
        procedure=procedure,
        prep_step=setup_data["critical_step"],
        scheduled_at=timezone.now() - timedelta(minutes=5),
        status="pending",
    )

    process_due_reminders()

    reminder.refresh_from_db()

    mock_send.assert_called_once()
    assert reminder.status == "pending"
    assert reminder.sent_at is None


@pytest.mark.django_db
@patch("notifications.tasks.send_reminder", return_value=True)
def test_already_sent_reminder_is_not_sent_again(mock_send, setup_data):
    procedure = setup_data["procedure"]

    reminder = Reminder.objects.create(
        procedure=procedure,
        prep_step=setup_data["critical_step"],
        scheduled_at=timezone.now() - timedelta(hours=3),
        sent_at=timezone.now() - timedelta(hours=2),
        status="sent",
    )

    process_due_reminders()

    reminder.refresh_from_db()

    mock_send.assert_not_called()
    assert reminder.status == "sent"


@pytest.mark.django_db
@patch("notifications.tasks.send_reminder", return_value=False)
def test_failed_delivery_increments_attempt_count(mock_send, setup_data):
    procedure = setup_data["procedure"]

    reminder = Reminder.objects.create(
        procedure=procedure,
        prep_step=setup_data["critical_step"],
        scheduled_at=timezone.now() - timedelta(minutes=5),
        status="pending",
    )

    process_due_reminders()

    reminder.refresh_from_db()

    assert reminder.status == "pending"
    assert reminder.delivery_attempts == 1
    assert reminder.sent_at is None
    mock_send.assert_called_once()


@pytest.mark.django_db
@patch("notifications.tasks.send_reminder", side_effect=RuntimeError("Test failure"))
def test_delivery_exception_is_logged_and_counted(mock_send, setup_data, caplog):
    import logging

    procedure = setup_data["procedure"]

    reminder = Reminder.objects.create(
        procedure=procedure,
        prep_step=setup_data["critical_step"],
        scheduled_at=timezone.now() - timedelta(minutes=5),
        status="pending",
    )

    with caplog.at_level(logging.ERROR, logger="notifications.tasks"):
        process_due_reminders()

    reminder.refresh_from_db()

    assert reminder.status == "pending"
    assert reminder.delivery_attempts == 1
    assert "delivery raised an exception" in caplog.text
    mock_send.assert_called_once()


@pytest.mark.django_db
@patch("notifications.tasks.send_reminder", return_value=False)
def test_third_failed_attempt_marks_reminder_failed(mock_send, setup_data):
    procedure = setup_data["procedure"]

    reminder = Reminder.objects.create(
        procedure=procedure,
        prep_step=setup_data["critical_step"],
        scheduled_at=timezone.now() - timedelta(minutes=5),
        status="pending",
        delivery_attempts=2,
    )

    process_due_reminders()

    reminder.refresh_from_db()

    assert reminder.status == "failed"
    assert reminder.delivery_attempts == 3
    assert reminder.sent_at is None
    mock_send.assert_called_once()



@pytest.mark.django_db
@patch(
    "notifications.tasks.send_reminder",
    return_value=False,
)
def test_first_failure_schedules_retry_after_five_minutes(
    mock_send, setup_data
):
    procedure = setup_data["procedure"]
    before_attempt = timezone.now()

    reminder = Reminder.objects.create(
        procedure=procedure,
        prep_step=setup_data["critical_step"],
        scheduled_at=before_attempt - timedelta(minutes=5),
        status="pending",
    )

    process_due_reminders()

    reminder.refresh_from_db()

    mock_send.assert_called_once()
    assert reminder.status == "pending"
    assert reminder.delivery_attempts == 1
    assert reminder.next_attempt_at is not None
    assert before_attempt + timedelta(minutes=5) <= reminder.next_attempt_at
    assert reminder.next_attempt_at <= timezone.now() + timedelta(minutes=5)


@pytest.mark.django_db
@patch(
    "notifications.tasks.send_reminder",
    return_value=False,
)
def test_second_failure_schedules_retry_after_fifteen_minutes(
    mock_send, setup_data
):
    procedure = setup_data["procedure"]
    before_attempt = timezone.now()

    reminder = Reminder.objects.create(
        procedure=procedure,
        prep_step=setup_data["critical_step"],
        scheduled_at=before_attempt - timedelta(minutes=5),
        status="pending",
        delivery_attempts=1,
    )

    process_due_reminders()

    reminder.refresh_from_db()

    mock_send.assert_called_once()
    assert reminder.status == "pending"
    assert reminder.delivery_attempts == 2
    assert reminder.next_attempt_at is not None
    assert before_attempt + timedelta(minutes=15) <= reminder.next_attempt_at
    assert reminder.next_attempt_at <= timezone.now() + timedelta(minutes=15)


@pytest.mark.django_db
@patch(
    "notifications.tasks.send_reminder",
    return_value={"messageId": "mock-message-id", "timestamp": 1234567890},
)
def test_reminder_waiting_for_retry_is_not_claimed(mock_send, setup_data):
    procedure = setup_data["procedure"]

    reminder = Reminder.objects.create(
        procedure=procedure,
        prep_step=setup_data["critical_step"],
        scheduled_at=timezone.now() - timedelta(minutes=10),
        next_attempt_at=timezone.now() + timedelta(minutes=5),
        status="pending",
        delivery_attempts=1,
    )

    process_due_reminders()

    reminder.refresh_from_db()

    mock_send.assert_not_called()
    assert reminder.status == "pending"
    assert reminder.delivery_attempts == 1
    assert reminder.sent_at is None
