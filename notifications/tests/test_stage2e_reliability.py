from datetime import timedelta

import pytest
from django.utils import timezone

from notifications.tasks import (
    REMINDER_CLAIM_LEASE,
    _claim_reminder,
    _schedule_retry,
    _update_claimed_reminder,
)
from reminders.models import Reminder
from .test_missed_reminders import setup_data


@pytest.mark.django_db
def test_reminder_cannot_be_claimed_twice_during_active_lease(setup_data):
    reminder = Reminder.objects.create(
        procedure=setup_data["procedure"],
        prep_step=setup_data["critical_step"],
        scheduled_at=timezone.now() - timedelta(minutes=5),
        status="pending",
    )

    now = timezone.now()
    first_claim = _claim_reminder(reminder.id, now)
    second_claim = _claim_reminder(reminder.id, now + timedelta(seconds=1))

    assert first_claim is not None
    assert first_claim.delivery_attempts == 1
    assert second_claim is None

    reminder.refresh_from_db()
    assert reminder.delivery_attempts == 1
    assert reminder.next_attempt_at is not None
    assert reminder.next_attempt_at >= now + REMINDER_CLAIM_LEASE


@pytest.mark.django_db
def test_expired_reminder_claim_can_be_recovered(setup_data):
    reminder = Reminder.objects.create(
        procedure=setup_data["procedure"],
        prep_step=setup_data["critical_step"],
        scheduled_at=timezone.now() - timedelta(minutes=5),
        status="pending",
    )

    now = timezone.now()
    first_claim = _claim_reminder(reminder.id, now)
    recovered_claim = _claim_reminder(
        reminder.id,
        now + REMINDER_CLAIM_LEASE + timedelta(seconds=1),
    )

    assert first_claim is not None
    assert recovered_claim is not None
    assert recovered_claim.delivery_attempts == 2


@pytest.mark.django_db
def test_retry_replaces_claim_lease_with_retry_delay(setup_data):
    reminder = Reminder.objects.create(
        procedure=setup_data["procedure"],
        prep_step=setup_data["critical_step"],
        scheduled_at=timezone.now() - timedelta(minutes=5),
        status="pending",
    )

    claimed = _claim_reminder(reminder.id, timezone.now())
    assert claimed is not None

    before_retry = timezone.now()
    _schedule_retry(claimed)
    reminder.refresh_from_db()

    assert reminder.status == "pending"
    assert reminder.next_attempt_at is not None
    assert before_retry + timedelta(minutes=5) <= reminder.next_attempt_at


@pytest.mark.django_db
def test_stale_reminder_worker_cannot_mark_newer_claim_as_sent(setup_data):
    reminder = Reminder.objects.create(
        procedure=setup_data["procedure"],
        prep_step=setup_data["critical_step"],
        scheduled_at=timezone.now() - timedelta(minutes=5),
        status="pending",
    )

    now = timezone.now()
    stale_claim = _claim_reminder(reminder.id, now)
    newer_claim = _claim_reminder(
        reminder.id,
        now + REMINDER_CLAIM_LEASE + timedelta(seconds=1),
    )

    assert stale_claim is not None
    assert newer_claim is not None
    assert newer_claim.delivery_attempts == 2

    updated = _update_claimed_reminder(
        stale_claim,
        status="sent",
        sent_at=timezone.now(),
        next_attempt_at=None,
        delivery_status="accepted",
        openwa_message_id="stale-worker-message",
    )

    assert updated is False

    reminder.refresh_from_db()
    assert reminder.status == "pending"
    assert reminder.delivery_attempts == 2
    assert reminder.next_attempt_at == newer_claim.next_attempt_at
    assert reminder.openwa_message_id in (None, "")


@pytest.mark.django_db
def test_stale_reminder_worker_cannot_schedule_retry_over_newer_claim(setup_data):
    reminder = Reminder.objects.create(
        procedure=setup_data["procedure"],
        prep_step=setup_data["critical_step"],
        scheduled_at=timezone.now() - timedelta(minutes=5),
        status="pending",
    )

    now = timezone.now()
    stale_claim = _claim_reminder(reminder.id, now)
    newer_claim = _claim_reminder(
        reminder.id,
        now + REMINDER_CLAIM_LEASE + timedelta(seconds=1),
    )

    assert stale_claim is not None
    assert newer_claim is not None
    assert newer_claim.delivery_attempts == 2

    scheduled = _schedule_retry(stale_claim)

    assert scheduled is False

    reminder.refresh_from_db()
    assert reminder.status == "pending"
    assert reminder.delivery_attempts == 2
    assert reminder.next_attempt_at == newer_claim.next_attempt_at
