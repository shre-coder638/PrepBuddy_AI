
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
