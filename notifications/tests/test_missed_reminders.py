
from datetime import timedelta

import pytest
from django.utils import timezone
from django.db.models.query import QuerySet
from unittest.mock import patch

from patients.models import Patient
from procedures.models import Procedure
from protocols.models import PrepProtocol, PrepStep
from reminders.models import Reminder
from notifications.tasks import check_missed_reminders

@pytest.fixture
def setup_data(db):
    """Create a patient, protocol, steps, and procedure for testing."""
    patient = Patient.objects.create(
        first_name="Test",
        last_name="Patient",
        phone_number="+910000000001",
        email="test@example.com",
    )

    protocol = PrepProtocol.objects.create(
        name="Test Protocol",
        description="Protocol for automated tests",
    )

    critical_step = PrepStep.objects.create(
        protocol=protocol,
        title="Critical preparation",
        instruction="Complete the critical preparation step.",
        minutes_before_procedure=120,
        is_critical=True,
    )

    noncritical_step = PrepStep.objects.create(
        protocol=protocol,
        title="Noncritical preparation",
        instruction="Complete the noncritical preparation step.",
        minutes_before_procedure=60,
        is_critical=False,
    )

    procedure = Procedure.objects.create(
        patient=patient,
        protocol=protocol,
        procedure_name="Test Procedure",
        scheduled_at=timezone.now() + timedelta(days=1),
        status="prep_in_progress",
    )

    return {
        "procedure": procedure,
        "critical_step": critical_step,
        "noncritical_step": noncritical_step,
    }

def create_reminder(procedure, step, status, sent_at=None):
    return Reminder.objects.create(
        procedure=procedure,
        prep_step=step,
        scheduled_at=timezone.now() - timedelta(hours=3),
        sent_at=sent_at,
        status=status,
    )

@pytest.mark.django_db
def test_old_sent_critical_reminder_marks_procedure_attention_needed(
    setup_data,
):
    procedure = setup_data["procedure"]

    create_reminder(
        procedure,
        setup_data["critical_step"],
        "sent",
        sent_at=timezone.now() - timedelta(hours=3),
    )

    check_missed_reminders()

    procedure.refresh_from_db()
    reminder = Reminder.objects.get(procedure=procedure)

    assert reminder.status == "missed"
    assert procedure.status == "attention_needed"

@pytest.mark.django_db
def test_old_sent_noncritical_reminder_does_not_flag_procedure(
    setup_data,
):
    procedure = setup_data["procedure"]

    create_reminder(
        procedure,
        setup_data["noncritical_step"],
        "sent",
        sent_at=timezone.now() - timedelta(hours=3),
    )

    check_missed_reminders()

    procedure.refresh_from_db()
    reminder = Reminder.objects.get(procedure=procedure)

    assert reminder.status == "missed"
    assert procedure.status == "prep_in_progress"

@pytest.mark.django_db
@pytest.mark.parametrize("status", ["cancelled", "completed"])
def test_terminal_procedure_status_is_preserved(setup_data, status):
    procedure = setup_data["procedure"]
    procedure.status = status
    procedure.save(update_fields=["status", "updated_at"])

    create_reminder(
        procedure,
        setup_data["critical_step"],
        "missed",
    )

    check_missed_reminders()

    procedure.refresh_from_db()
    assert procedure.status == status

@pytest.mark.django_db
def test_ready_procedure_is_corrected_for_missed_critical_reminder(
    setup_data,
):
    procedure = setup_data["procedure"]
    procedure.status = "ready"
    procedure.save(update_fields=["status", "updated_at"])

    create_reminder(
        procedure,
        setup_data["critical_step"],
        "missed",
    )

    check_missed_reminders()

    procedure.refresh_from_db()
    assert procedure.status == "attention_needed"

@pytest.mark.django_db
def test_recent_sent_reminder_is_not_marked_missed(setup_data):
    procedure = setup_data["procedure"]

    create_reminder(
        procedure,
        setup_data["critical_step"],
        "sent",
        sent_at=timezone.now() - timedelta(minutes=30),
    )

    check_missed_reminders()

    procedure.refresh_from_db()
    reminder = Reminder.objects.get(procedure=procedure)

    assert reminder.status == "sent"
    assert procedure.status == "prep_in_progress"

@pytest.mark.django_db
def test_pending_reminder_is_missed_after_procedure_time(setup_data):
    procedure = setup_data["procedure"]
    procedure.scheduled_at = timezone.now() - timedelta(minutes=1)
    procedure.save(update_fields=["scheduled_at", "updated_at"])

    reminder = create_reminder(
        procedure,
        setup_data["noncritical_step"],
        "pending",
    )

    check_missed_reminders()

    reminder.refresh_from_db()
    procedure.refresh_from_db()

    assert reminder.status == "missed"

@pytest.mark.django_db
def test_past_procedure_with_pending_critical_reminder_needs_attention(
    setup_data,
):
    procedure = setup_data["procedure"]
    procedure.scheduled_at = timezone.now() - timedelta(minutes=1)
    procedure.save(update_fields=["scheduled_at", "updated_at"])

    reminder = create_reminder(
        procedure,
        setup_data["critical_step"],
        "pending",
    )

    check_missed_reminders()

    reminder.refresh_from_db()
    procedure.refresh_from_db()

    assert reminder.status == "missed"
    assert procedure.status == "attention_needed"

@pytest.mark.django_db
def test_pending_reminder_for_future_procedure_stays_pending(setup_data):
    procedure = setup_data["procedure"]
    procedure.scheduled_at = timezone.now() + timedelta(hours=1)
    procedure.save(update_fields=["scheduled_at", "updated_at"])

    reminder = create_reminder(
        procedure,
        setup_data["noncritical_step"],
        "pending",
    )

    check_missed_reminders()

    reminder.refresh_from_db()

    assert reminder.status == "pending"

@pytest.mark.django_db
@pytest.mark.parametrize("status", ["cancelled", "completed"])
def test_past_procedure_does_not_change_terminal_status(
    setup_data, status
):
    procedure = setup_data["procedure"]
    procedure.scheduled_at = timezone.now() - timedelta(minutes=1)
    procedure.status = status
    procedure.save(update_fields=["scheduled_at", "status", "updated_at"])

    create_reminder(
        procedure,
        setup_data["critical_step"],
        "pending",
    )

    check_missed_reminders()

    procedure.refresh_from_db()

    assert procedure.status == status

@pytest.mark.django_db
def test_all_confirmed_reminders_reconcile_scheduled_procedure_to_ready(
    setup_data,
):
    procedure = setup_data["procedure"]
    procedure.status = "scheduled"
    procedure.save(update_fields=["status", "updated_at"])

    create_reminder(
        procedure,
        setup_data["critical_step"],
        "confirmed",
    )
    create_reminder(
        procedure,
        setup_data["noncritical_step"],
        "confirmed",
    )

    check_missed_reminders()

    procedure.refresh_from_db()
    assert procedure.status == "ready"



@pytest.mark.django_db
def test_pending_reminder_transition_does_not_overwrite_concurrent_change(
    setup_data,
):
    procedure = setup_data["procedure"]
    procedure.scheduled_at = timezone.now() - timedelta(minutes=1)
    procedure.save(update_fields=["scheduled_at", "updated_at"])

    reminder = create_reminder(
        procedure,
        setup_data["critical_step"],
        "pending",
    )

    original_update = QuerySet.update
    competing_change_applied = False

    def apply_competing_change(queryset, **kwargs):
        nonlocal competing_change_applied

        if kwargs.get("status") == "missed" and not competing_change_applied:
            competing_change_applied = True
            original_update(
                Reminder.objects.filter(pk=reminder.pk),
                status="confirmed",
                confirmed_at=timezone.now(),
            )

        return original_update(queryset, **kwargs)

    with patch.object(QuerySet, "update", new=apply_competing_change):
        check_missed_reminders()

    reminder.refresh_from_db()

    assert competing_change_applied is True
    assert reminder.status == "confirmed"
    assert reminder.confirmed_at is not None
    assert not hasattr(reminder, "staff_alert")

@pytest.mark.django_db
def test_done_confirmation_wins_race_with_missed_reminder_check(setup_data):
    procedure = setup_data["procedure"]
    reminder = create_reminder(
        procedure,
        setup_data["critical_step"],
        "sent",
        sent_at=timezone.now() - timedelta(hours=3),
    )

    original_update = QuerySet.update
    competing_confirmation_applied = False

    def apply_competing_confirmation(queryset, **kwargs):
        nonlocal competing_confirmation_applied

        if kwargs == {"status": "missed"} and not competing_confirmation_applied:
            competing_confirmation_applied = True
            original_update(
                Reminder.objects.filter(pk=reminder.pk),
                status="confirmed",
                confirmed_at=timezone.now(),
            )

        return original_update(queryset, **kwargs)

    with patch.object(QuerySet, "update", new=apply_competing_confirmation):
        check_missed_reminders()

    reminder.refresh_from_db()
    procedure.refresh_from_db()

    assert competing_confirmation_applied is True
    assert reminder.status == "confirmed"
    assert reminder.confirmed_at is not None
    assert procedure.status != "attention_needed"
    assert not hasattr(reminder, "staff_alert")



@pytest.mark.django_db
def test_bounded_missed_batches_progress(setup_data):
    from notifications.models import MissedReminderAlert

    procedure = setup_data["procedure"]
    old = timezone.now() - timedelta(hours=3)

    first = create_reminder(
        procedure,
        setup_data["noncritical_step"],
        "sent",
        sent_at=old,
    )

    second = create_reminder(
        procedure,
        setup_data["critical_step"],
        "sent",
        sent_at=old,
    )

    check_missed_reminders.run(batch_size=1)

    first.refresh_from_db()
    second.refresh_from_db()

    assert first.status == "missed"
    assert second.status == "sent"

    assert MissedReminderAlert.objects.filter(
        reminder=first,
    ).count() == 1

    assert not MissedReminderAlert.objects.filter(
        reminder=second,
    ).exists()

    check_missed_reminders.run(batch_size=1)

    second.refresh_from_db()
    procedure.refresh_from_db()

    assert second.status == "missed"
    assert procedure.status == "attention_needed"

    assert MissedReminderAlert.objects.filter(
        reminder_id__in=[first.pk, second.pk],
    ).count() == 2

    # Repeated execution must not create duplicate alerts.
    check_missed_reminders.run(batch_size=1)

    assert MissedReminderAlert.objects.filter(
        reminder_id__in=[first.pk, second.pk],
    ).count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize("initial_status", [
    "sent",
    "pending",
])
def test_missed_transition_rolls_back_on_alert_failure(
    setup_data,
    initial_status,
):
    from notifications import tasks
    from notifications.models import MissedReminderAlert

    procedure = setup_data["procedure"]

    if initial_status == "pending":
        procedure.scheduled_at = (
            timezone.now() - timedelta(minutes=10)
        )

        procedure.save(update_fields=["scheduled_at"])

    reminder = create_reminder(
        procedure,
        setup_data["critical_step"],
        initial_status,
        sent_at=(
            timezone.now() - timedelta(hours=3)
            if initial_status == "sent"
            else None
        ),
    )

    original_queue = tasks._queue_missed_reminder_alert

    def create_then_fail(reminder):
        original_queue(reminder)
        raise RuntimeError("Synthetic alert transaction failure")

    with patch.object(
        tasks,
        "_queue_missed_reminder_alert",
        side_effect=create_then_fail,
    ):
        with pytest.raises(
            RuntimeError,
            match="Synthetic alert transaction failure",
        ):
            check_missed_reminders.run(batch_size=1)

    reminder.refresh_from_db()
    procedure.refresh_from_db()

    assert reminder.status == initial_status
    assert procedure.status == "prep_in_progress"

    assert not MissedReminderAlert.objects.filter(
        reminder=reminder,
    ).exists()

    # A subsequent successful tick must recover normally.
    check_missed_reminders.run(batch_size=1)

    reminder.refresh_from_db()
    procedure.refresh_from_db()

    assert reminder.status == "missed"
    assert procedure.status == "attention_needed"

    assert MissedReminderAlert.objects.filter(
        reminder=reminder,
    ).count() == 1


@pytest.mark.django_db
def test_bounded_reconciliation_does_not_starve(
    setup_data,
):
    first = setup_data["procedure"]

    first.status = "ready"
    first.save(update_fields=["status"])

    create_reminder(
        first,
        setup_data["noncritical_step"],
        "confirmed",
    )

    procedures = []

    for index in range(2):
        procedure = Procedure.objects.create(
            patient=first.patient,
            protocol=first.protocol,
            procedure_name=f"Synthetic procedure {index}",
            scheduled_at=(
                timezone.now() + timedelta(days=1)
            ),
            status="scheduled",
        )

        create_reminder(
            procedure,
            setup_data["noncritical_step"],
            "confirmed",
        )

        procedures.append(procedure)

    check_missed_reminders.run(batch_size=1)

    for procedure in procedures:
        procedure.refresh_from_db()

    assert procedures[0].status == "ready"
    assert procedures[1].status == "scheduled"

    check_missed_reminders.run(batch_size=1)

    for procedure in procedures:
        procedure.refresh_from_db()

    assert all(
        procedure.status == "ready"
        for procedure in procedures
    )



@pytest.mark.django_db
def test_bounded_alert_retry_progress(setup_data, settings):
    from types import SimpleNamespace
    from notifications import tasks
    from notifications.models import MissedReminderAlert

    settings.WHATSAPP_SEND_ENABLED = True

    alerts = []

    for step in (
        setup_data["critical_step"],
        setup_data["noncritical_step"],
    ):
        reminder = create_reminder(
            setup_data["procedure"],
            step,
            "missed",
        )

        alerts.append(
            MissedReminderAlert.objects.create(
                reminder=reminder,
            )
        )

    first, second = alerts

    doctor = SimpleNamespace(
        pk=1,
        phone_number="+910000000001",
    )

    success = {
        "success": True,
        "messageId": "synthetic-message",
    }

    with patch.object(
        tasks.StaffProfile.objects,
        "filter",
    ) as staff, patch.object(
        tasks,
        "send_openwa_message",
        side_effect=[
            RuntimeError("Synthetic delivery failure"),
            success,
            success,
        ],
    ) as send:

        staff.return_value.exclude.return_value.order_by.return_value = [
            doctor
        ]

        # First alert fails and enters cooldown.
        tasks._send_pending_missed_reminder_whatsapp_alerts(
            batch_size=1,
        )

        first.refresh_from_db()
        second.refresh_from_db()

        assert first.whatsapp_sent_at is None
        assert first.whatsapp_next_attempt_at > timezone.now()
        assert second.whatsapp_sent_at is None
        assert send.call_count == 1

        # Second alert progresses despite the first failure.
        tasks._send_pending_missed_reminder_whatsapp_alerts(
            batch_size=1,
        )

        second.refresh_from_db()

        assert second.whatsapp_sent_at is not None
        assert second.whatsapp_next_attempt_at is None
        assert send.call_count == 2

        # First alert is still cooling down.
        tasks._send_pending_missed_reminder_whatsapp_alerts(
            batch_size=1,
        )

        assert send.call_count == 2

        # Simulate retry cooldown expiration.
        MissedReminderAlert.objects.filter(
            pk=first.pk,
        ).update(
            whatsapp_next_attempt_at=(
                timezone.now() - timedelta(seconds=1)
            ),
        )

        tasks._send_pending_missed_reminder_whatsapp_alerts(
            batch_size=1,
        )

        first.refresh_from_db()

        assert first.whatsapp_sent_at is not None
        assert first.whatsapp_next_attempt_at is None
        assert send.call_count == 3

        # Completed alerts must not be sent again.
        tasks._send_pending_missed_reminder_whatsapp_alerts(
            batch_size=1,
        )

        assert send.call_count == 3


@pytest.mark.parametrize("batch_size", [
    0, -1, 11, True, "1", 1.5,
])
def test_invalid_whatsapp_alert_batch(batch_size):
    from notifications import tasks

    with pytest.raises(ValueError):
        tasks._send_pending_missed_reminder_whatsapp_alerts(
            batch_size=batch_size,
        )


@pytest.mark.django_db
def test_bounded_alert_recipient_limit(setup_data, settings):
    from types import SimpleNamespace
    from notifications import tasks
    from notifications.models import MissedReminderAlert

    settings.WHATSAPP_SEND_ENABLED = True

    reminder = create_reminder(
        setup_data["procedure"],
        setup_data["critical_step"],
        "missed",
    )

    alert = MissedReminderAlert.objects.create(
        reminder=reminder,
    )

    doctors = [
        SimpleNamespace(
            pk=index,
            phone_number="+910000000001",
        )
        for index in range(1, 4)
    ]

    with patch.object(
        tasks.StaffProfile.objects,
        "filter",
    ) as staff, patch.object(
        tasks,
        "send_openwa_message",
    ) as send:

        staff.return_value.exclude.return_value.order_by.return_value = (
            doctors
        )

        tasks._send_pending_missed_reminder_whatsapp_alerts(
            batch_size=1,
        )

        send.assert_not_called()

    alert.refresh_from_db()

    assert alert.whatsapp_sent_at is None
    assert alert.whatsapp_next_attempt_at is None



@pytest.mark.django_db
@pytest.mark.parametrize("success", [True, False])
def test_stale_whatsapp_alert_worker(
    setup_data,
    settings,
    success,
):
    from types import SimpleNamespace
    from notifications import tasks
    from notifications.models import MissedReminderAlert

    settings.WHATSAPP_SEND_ENABLED = True

    reminder = create_reminder(
        setup_data["procedure"],
        setup_data["critical_step"],
        "missed",
    )

    alert = MissedReminderAlert.objects.create(
        reminder=reminder,
    )

    new_claim = timezone.now() + timedelta(minutes=15)

    doctor = SimpleNamespace(
        pk=1,
        phone_number="+910000000001",
    )

    def lose_claim(*args, **kwargs):
        MissedReminderAlert.objects.filter(
            pk=alert.pk,
        ).update(
            whatsapp_next_attempt_at=new_claim,
            whatsapp_last_error="New owner state",
        )

        if not success:
            raise RuntimeError("Stale worker failure")

        return {
            "success": True,
            "messageId": "synthetic-message",
        }

    with patch.object(
        tasks.StaffProfile.objects,
        "filter",
    ) as staff, patch.object(
        tasks,
        "send_openwa_message",
        side_effect=lose_claim,
    ):

        staff.return_value.exclude.return_value.order_by.return_value = [
            doctor
        ]

        tasks._send_pending_missed_reminder_whatsapp_alerts(
            batch_size=1,
        )

    alert.refresh_from_db()

    assert alert.whatsapp_sent_at is None
    assert alert.whatsapp_next_attempt_at == new_claim
    assert alert.whatsapp_last_error == "New owner state"


@pytest.mark.django_db
@pytest.mark.parametrize("status", [
    "cancelled",
    "completed",
])
def test_stale_critical_update_preserves_terminal_status(
    setup_data,
    status,
):
    from notifications.tasks import (
        _mark_procedure_attention_needed,
    )

    procedure = setup_data["procedure"]

    Procedure.objects.filter(
        pk=procedure.pk,
    ).update(status=status)

    assert not _mark_procedure_attention_needed(procedure)

    procedure.refresh_from_db()

    assert procedure.status == status


@pytest.mark.django_db
@pytest.mark.parametrize("status", [
    "cancelled",
    "completed",
    "attention_needed",
])
def test_stale_reconciliation_preserves_current_status(
    setup_data,
    status,
):
    from reminders.views import sync_procedure_status

    procedure = setup_data["procedure"]

    create_reminder(
        procedure,
        setup_data["noncritical_step"],
        "confirmed",
    )

    Procedure.objects.filter(
        pk=procedure.pk,
    ).update(status=status)

    sync_procedure_status(procedure)

    assert procedure.status == status

    procedure.refresh_from_db()

    assert procedure.status == status
