from datetime import timedelta
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone

from frontend.models import StaffProfile
from procedures.models import Procedure
from reminders.models import Reminder
from reminders.views import sync_procedure_status
from .models import MissedReminderAlert
from .services import send_reminder
from .whatsapp import send_openwa_message

logger = logging.getLogger(__name__)

MAX_DELIVERY_ATTEMPTS = 3
MISSED_ALERT_EMAIL_CLAIM_LEASE = timedelta(minutes=5)

# A pending reminder is temporarily hidden from other workers while this
# timestamp is in the future. If a worker crashes, it becomes eligible again
# after the lease expires. Keep this comfortably above the OpenWA HTTP timeout.
REMINDER_CLAIM_LEASE = timedelta(minutes=3)

RETRY_DELAYS_MINUTES = {
    1: 5,
    2: 15,
}

def _claim_reminder(reminder_id, now):
    """Atomically claim one eligible pending reminder."""
    with transaction.atomic():

        updated = (
            Reminder.objects.filter(
                id=reminder_id,
                status="pending",
                scheduled_at__lte=now,
                delivery_attempts__lt=MAX_DELIVERY_ATTEMPTS,
                procedure__scheduled_at__gt=now,
            )
            .exclude(
                procedure__status__in=[
                    "cancelled",
                    "completed",
                    "attention_needed",
                ]
            )
            .filter(
                models.Q(next_attempt_at__isnull=True)
                | models.Q(next_attempt_at__lte=now)
            )
            # Reuse the existing retry timestamp as a short claim lease. The
            # conditional UPDATE is atomic: only one worker can move it into
            # the future and increment the attempt counter.
            .update(
                delivery_attempts=F("delivery_attempts") + 1,
                next_attempt_at=now + REMINDER_CLAIM_LEASE,
            )
        )

        if updated != 1:
            return None

        return Reminder.objects.select_related(
            "procedure__patient",
            "prep_step",
        ).get(id=reminder_id)


def _update_claimed_reminder(reminder, **updates):
    """Update a reminder only while this worker still owns its claim."""
    updated = Reminder.objects.filter(
        pk=reminder.pk,
        status="pending",
        next_attempt_at=reminder.next_attempt_at,
        delivery_attempts=reminder.delivery_attempts,
    ).update(**updates)

    if updated == 1:
        for field, value in updates.items():
            setattr(reminder, field, value)
        return True

    return False


@shared_task
def process_due_reminders(*, batch_size=None):

    if (
        getattr(settings, "STAGING_MODE", False)
        and batch_size is None
    ):
        logger.warning("Legacy scheduler disabled in staging.")
        return

    if batch_size is not None and (
        type(batch_size) is not int
        or not 1 <= batch_size <= 10
    ):
        raise ValueError("Invalid reminder batch size")

    if not getattr(settings, "WHATSAPP_SEND_ENABLED", False):
        logger.info("Scheduled WhatsApp reminder delivery is disabled.")
        return

    now = timezone.now()

    stale_cutoff = now - timedelta(hours=2)

    due_query = (
        Reminder.objects.filter(
            status="pending",
            delivery_attempts__lt=MAX_DELIVERY_ATTEMPTS,
            scheduled_at__lte=now,
            scheduled_at__gte=stale_cutoff,
            procedure__scheduled_at__gt=now,
        )
        .filter(
            models.Q(next_attempt_at__isnull=True)
            | models.Q(next_attempt_at__lte=now)
        )
        .exclude(
            procedure__status__in=["cancelled", "completed", "attention_needed"]
        )
        .order_by("id")
        .values_list("id", flat=True)
    )

    if batch_size is not None:
        due_query = due_query[:batch_size]

    due_ids = list(due_query)

    for reminder_id in due_ids:
        reminder = _claim_reminder(reminder_id, timezone.now())

        # Another worker may already have claimed or changed it.
        if reminder is None:
            continue

        try:
            result = send_reminder(reminder)

            if isinstance(result, dict) and result:
                message_id = result.get("messageId")
                success_updates = {
                    "status": "sent",
                    "sent_at": timezone.now(),
                    "next_attempt_at": None,
                    "delivery_status": "accepted" if message_id else "unknown",
                }
                if message_id:
                    success_updates["openwa_message_id"] = str(message_id)

                updated = _update_claimed_reminder(
                    reminder,
                    **success_updates,
                )

                if not updated:
                    logger.warning(
                        "Reminder %s delivery completed, but this worker "
                        "no longer owns its claim. The newer claim was preserved.",
                        reminder.id,
                    )
                else:
                    if not message_id:
                        logger.warning(
                            "OpenWA accepted reminder %s but returned no messageId; "
                            "delivery acknowledgements cannot be matched reliably.",
                            reminder.id,
                        )

                    logger.info(
                        "Reminder %s accepted by OpenWA on attempt %s. "
                        "Message ID available: %s. Recipient delivery is not yet "
                        "confirmed.",
                        reminder.id,
                        reminder.delivery_attempts,
                        bool(message_id),
                    )
            else:
                _schedule_retry(reminder)

                logger.warning(
                    "Reminder %s received an empty or invalid response "
                    "on attempt %s of %s.",
                    reminder.id,
                    reminder.delivery_attempts,
                    MAX_DELIVERY_ATTEMPTS,
                )

        except Exception:
            _schedule_retry(reminder)

            logger.exception(
                "Reminder %s delivery raised an exception "
                "on attempt %s of %s.",
                reminder.id,
                reminder.delivery_attempts,
                MAX_DELIVERY_ATTEMPTS,
            )

def _schedule_retry(reminder):
    if reminder.delivery_attempts >= MAX_DELIVERY_ATTEMPTS:
        status = "failed"
        next_attempt_at = None
    else:
        # Replace this worker's temporary claim lease with the normal retry delay.
        status = "pending"
        delay_minutes = RETRY_DELAYS_MINUTES.get(
            reminder.delivery_attempts,
            15,
        )
        next_attempt_at = (
            timezone.now() + timedelta(minutes=delay_minutes)
        )

    updated = _update_claimed_reminder(
        reminder,
        status=status,
        next_attempt_at=next_attempt_at,
    )

    if not updated:
        logger.warning(
            "Reminder %s retry was not scheduled because this worker "
            "no longer owns its claim.",
            reminder.id,
        )
        return False

    if status == "failed":
        logger.error(
            "Reminder %s exhausted its delivery attempts.",
            reminder.id,
        )

    return True

def _mark_procedure_attention_needed(procedure):
    """Preserve terminal procedure states during reconciliation."""

    updated = Procedure.objects.filter(
        pk=procedure.pk,
    ).exclude(
        status__in=[
            "cancelled",
            "completed",
            "attention_needed",
        ],
    ).update(
        status="attention_needed",
        updated_at=timezone.now(),
    )

    if updated:
        procedure.status = "attention_needed"

    return updated == 1


def _queue_missed_reminder_alert(reminder):
    """Create one persistent staff alert per missed reminder."""
    alert, created = MissedReminderAlert.objects.get_or_create(
        reminder=reminder,
    )

    if created:
        logger.warning(
            "Created staff alert for missed reminder %s.",
            reminder.id,
        )

    return alert


def _send_pending_missed_reminder_alerts():
    """Email staff using an atomic, recoverable claim lease."""
    if not getattr(settings, "EMAIL_SEND_ENABLED", False):
        logger.info("Missed reminder staff email delivery is disabled.")
        return

    alert_ids = list(
        MissedReminderAlert.objects.filter(
            email_sent_at__isnull=True,
        ).values_list("pk", flat=True)
    )

    for alert_id in alert_ids:
        claim_time = timezone.now()
        expired_before = claim_time - MISSED_ALERT_EMAIL_CLAIM_LEASE

        # First claim alerts that have never been claimed.
        claimed = MissedReminderAlert.objects.filter(
            pk=alert_id,
            email_sent_at__isnull=True,
            email_claimed_at__isnull=True,
        ).update(email_claimed_at=claim_time)

        # Recover alerts whose previous worker's lease has expired.
        if claimed != 1:
            claimed = MissedReminderAlert.objects.filter(
                pk=alert_id,
                email_sent_at__isnull=True,
                email_claimed_at__lt=expired_before,
            ).update(email_claimed_at=claim_time)

        if claimed != 1:
            continue

        alert = MissedReminderAlert.objects.select_related(
            "reminder__procedure",
        ).get(pk=alert_id)

        recipients = list(
            StaffProfile.objects.filter(
                role__in=["clinic_staff", "doctor"],
                user__is_active=True,
            )
            .exclude(user__email="")
            .values_list("user__email", flat=True)
            .distinct()
        )

        if not recipients:
            released = MissedReminderAlert.objects.filter(
                pk=alert_id,
                email_sent_at__isnull=True,
                email_claimed_at=claim_time,
            ).update(
                last_error="No active staff email recipients configured.",
                email_claimed_at=None,
            )

            if released:
                logger.warning(
                    "No staff email recipients for missed reminder %s.",
                    alert.reminder_id,
                )
            continue

        reminder = alert.reminder
        procedure = reminder.procedure

        subject = (
            f"PrepBuddy: Missed reminder requires review "
            f"(Reminder #{reminder.id})"
        )
        message = (
            "A PrepBuddy preparation reminder has been marked as missed.\n\n"
            f"Reminder ID: {reminder.id}\n"
            f"Procedure ID: {procedure.id}\n"
            f"Procedure: {procedure.procedure_name}\n"
            f"Scheduled procedure time: {procedure.scheduled_at}\n\n"
            "Please open the PrepBuddy staff dashboard, contact the patient, "
            "record the follow-up outcome, and escalate for clinical review "
            "as appropriate.\n\n"
            "This alert does not establish whether preparation was completed "
            "and does not authorize proceeding with the procedure."
        )

        try:
            sent_count = send_mail(
                subject=subject,
                message=message,
                from_email=getattr(
                    settings,
                    "DEFAULT_FROM_EMAIL",
                    None,
                ),
                recipient_list=recipients,
                fail_silently=False,
            )

            if sent_count == 1:
                updated = MissedReminderAlert.objects.filter(
                    pk=alert_id,
                    email_sent_at__isnull=True,
                    email_claimed_at=claim_time,
                ).update(
                    email_sent_at=timezone.now(),
                    last_error="",
                    email_claimed_at=None,
                )

                if updated == 1:
                    logger.info(
                        "Staff alert email sent for missed reminder %s.",
                        reminder.id,
                    )
                else:
                    logger.warning(
                        "Email claim was lost before completion for "
                        "missed reminder %s.",
                        reminder.id,
                    )
            else:
                updated = MissedReminderAlert.objects.filter(
                    pk=alert_id,
                    email_sent_at__isnull=True,
                    email_claimed_at=claim_time,
                ).update(
                    last_error=(
                        "Email backend did not confirm a sent message."
                    ),
                    email_claimed_at=None,
                )

                if updated:
                    logger.warning(
                        "Staff alert email was not confirmed for reminder %s.",
                        reminder.id,
                    )

        except Exception as exc:
            MissedReminderAlert.objects.filter(
                pk=alert_id,
                email_sent_at__isnull=True,
                email_claimed_at=claim_time,
            ).update(
                last_error=str(exc)[:2000],
                email_claimed_at=None,
            )
            logger.exception(
                "Failed to email staff about missed reminder %s.",
                reminder.id,
            )


def _save_whatsapp_alert_result(alert, fields, claim_until):
    """Persist an alert result only while its claim is owned."""

    if claim_until is None:
        alert.save(update_fields=fields)
        return True

    updated = MissedReminderAlert.objects.filter(
        pk=alert.pk,
        whatsapp_sent_at__isnull=True,
        whatsapp_next_attempt_at=claim_until,
    ).update(
        **{
            field: getattr(alert, field)
            for field in fields
        }
    )

    if updated != 1:
        logger.warning(
            "WhatsApp alert %s claim ownership lost.",
            alert.pk,
        )

    return updated == 1


def _send_pending_missed_reminder_whatsapp_alerts(
    *, batch_size=None
):
    """Send pending doctor alerts with optional bounded retries."""

    if (
        getattr(settings, "STAGING_MODE", False)
        and batch_size is None
    ):
        logger.warning("Legacy scheduler disabled in staging.")
        return

    if batch_size is not None and (
        type(batch_size) is not int
        or not 1 <= batch_size <= 10
    ):
        raise ValueError("Invalid WhatsApp alert batch size")

    if not getattr(settings, "WHATSAPP_SEND_ENABLED", False):
        logger.info("Missed reminder WhatsApp alert delivery is disabled.")
        return

    alerts = MissedReminderAlert.objects.filter(
        whatsapp_sent_at__isnull=True,
    ).select_related(
        "reminder__procedure",
    )

    doctor_query = StaffProfile.objects.filter(
        role="doctor",
        user__is_active=True,
    ).exclude(
        phone_number="",
    )

    if batch_size is not None:
        now = timezone.now()

        alerts = (
            alerts.filter(
                models.Q(whatsapp_next_attempt_at__isnull=True)
                | models.Q(whatsapp_next_attempt_at__lte=now)
            )
            .order_by("pk")[:batch_size]
        )

        doctors = list(doctor_query.order_by("pk")[:3])

        if len(doctors) > 2:
            logger.warning(
                "Bounded doctor alert delivery requires "
                "at most two configured recipients."
            )
            return
    else:
        doctors = list(doctor_query)

    for alert in alerts:
        claim_until = None

        if batch_size is not None:
            claim_time = timezone.now()
            claim_until = claim_time + timedelta(minutes=5)

            claimed = MissedReminderAlert.objects.filter(
                pk=alert.pk,
                whatsapp_sent_at__isnull=True,
            ).filter(
                models.Q(whatsapp_next_attempt_at__isnull=True)
                | models.Q(
                    whatsapp_next_attempt_at__lte=claim_time
                )
            ).update(
                whatsapp_next_attempt_at=claim_until,
            )

            if claimed != 1:
                continue

        if not doctors:
            alert.whatsapp_last_error = (
                "No active doctors with phone numbers are configured."
            )
            if not _save_whatsapp_alert_result(
                alert,
                ["whatsapp_last_error"],
                claim_until,
            ):
                continue
            logger.warning(
                "No WhatsApp doctor recipients for missed reminder %s.",
                alert.reminder_id,
            )
            continue

        reminder = alert.reminder
        procedure = reminder.procedure

        message = (
            "PrepBuddy: A preparation reminder requires clinical review.\n\n"
            f"Reminder ID: {reminder.id}\n"
            f"Procedure ID: {procedure.id}\n"
            f"Scheduled procedure time: {procedure.scheduled_at}\n\n"
            "Please review the case in the PrepBuddy staff dashboard, "
            "contact the patient, record the follow-up outcome, and "
            "escalate for clinical review as appropriate.\n\n"
            "This alert does not confirm that preparation was completed "
            "and does not authorize proceeding with the procedure."
        )

        errors = []

        for doctor in doctors:
            # Normalize common phone-number formatting.
            phone = "".join(
                char
                for char in doctor.phone_number.strip()
                if char.isdigit()
            )

            if not 8 <= len(phone) <= 15:
                errors.append(
                    f"Doctor profile {doctor.pk}: invalid phone number."
                )
                continue

            try:
                result = send_openwa_message(
                    chat_id=f"{phone}@c.us",
                    text=message,
                    dedupe_key=f"missed-alert:{alert.pk}:doctor:{doctor.pk}",
                    purpose="missed_doctor_alert",
                )

                if not isinstance(result, dict) or not result:
                    raise RuntimeError(
                        "OpenWA returned an empty or invalid response."
                    )

                if (
                    result.get("success") is False
                    or result.get("sent") is False
                ):
                    raise RuntimeError(
                        "OpenWA reported a send failure."
                    )

            except Exception:
                logger.exception(
                    "WhatsApp alert failed for reminder %s and "
                    "doctor profile %s.",
                    reminder.id,
                    doctor.pk,
                )
                errors.append(
                    f"Doctor profile {doctor.pk}: send failed."
                )

        if errors:
            alert.whatsapp_last_error = "; ".join(errors)[:2000]
            if not _save_whatsapp_alert_result(
                alert,
                ["whatsapp_last_error"],
                claim_until,
            ):
                continue
            logger.warning(
                "WhatsApp alert for reminder %s remains pending.",
                reminder.id,
            )
        else:
            alert.whatsapp_sent_at = timezone.now()
            alert.whatsapp_last_error = ""
            alert.whatsapp_next_attempt_at = None
            if not _save_whatsapp_alert_result(
                alert,
                [
                    "whatsapp_sent_at",
                    "whatsapp_last_error",
                    "whatsapp_next_attempt_at",
                ],
                claim_until,
            ):
                continue
            logger.info(
                "OpenWA accepted doctor alert for missed reminder %s. "
                "Actual recipient delivery is not confirmed.",
                reminder.id,
            )

@shared_task
def check_missed_reminders(*, batch_size=None):
    """Reconcile missed reminders and preparation progress.

    Bounded execution performs database operations only.
    Unbounded legacy execution also retries external alerts.
    """

    if (
        getattr(settings, "STAGING_MODE", False)
        and batch_size is None
    ):
        logger.warning("Legacy scheduler disabled in staging.")
        return

    if batch_size is not None and (
        type(batch_size) is not int
        or not 1 <= batch_size <= 50
    ):
        raise ValueError("Invalid missed-reminder batch size")

    now = timezone.now()
    cutoff = now - timedelta(hours=2)

    # Mark sent reminders as missed if they remain unconfirmed.
    reminders = Reminder.objects.filter(
        status="sent",
        confirmed_at__isnull=True,
        sent_at__lte=cutoff,
    ).select_related("prep_step", "procedure")

    if batch_size is not None:
        reminders = reminders.order_by("pk")[:batch_size]

    for reminder in reminders:
        with transaction.atomic():
            updated = Reminder.objects.filter(
                pk=reminder.pk,
                status="sent",
                confirmed_at__isnull=True,
                sent_at__lte=cutoff,
            ).update(status="missed")

            if updated != 1:
                continue

            reminder.status = "missed"
            _queue_missed_reminder_alert(reminder)

            if reminder.prep_step.is_critical:
                procedure = reminder.procedure

                if procedure.status not in ["cancelled", "completed"]:
                    _mark_procedure_attention_needed(procedure)

                    logger.warning(
                        "A critical preparation reminder was missed; procedure %s requires attention.",
                        procedure.id,
                    )

    # Mark overdue pending reminders as missed once the procedure
    # itself has started or passed. Do not process reminders for
    # cancelled or completed procedures.
    overdue_pending = Reminder.objects.filter(
        status="pending",
        scheduled_at__lte=now,
        procedure__scheduled_at__lte=now,
    ).exclude(
        procedure__status__in=["cancelled", "completed"]
    ).select_related("prep_step", "procedure")

    if batch_size is not None:
        overdue_pending = (
            overdue_pending.order_by("pk")[:batch_size]
        )

    for reminder in overdue_pending:
        with transaction.atomic():
            updated = Reminder.objects.filter(
                pk=reminder.pk,
                status="pending",
                scheduled_at__lte=now,
                procedure__scheduled_at__lte=now,
            ).exclude(
                procedure__status__in=["cancelled", "completed"]
            ).update(
                status="missed",
                next_attempt_at=None,
            )

            if updated != 1:
                continue

            reminder.status = "missed"
            reminder.next_attempt_at = None
            _queue_missed_reminder_alert(reminder)

            if reminder.prep_step.is_critical:
                procedure = reminder.procedure

                if procedure.status != "attention_needed":
                    _mark_procedure_attention_needed(procedure)

                logger.warning(
                    "Critical pending reminder %s became overdue. "
                    "Procedure %s requires attention.",
                    reminder.id,
                    procedure.id,
                )

    # Reconcile existing missed critical reminders as well.
    # This also catches a procedure incorrectly changed back to "ready".
    affected_procedure_ids = (
        Reminder.objects.filter(
            status="missed",
            prep_step__is_critical=True,
        )
        .values_list("procedure_id", flat=True)
        .distinct()
    )

    affected_procedures = Procedure.objects.filter(
        id__in=affected_procedure_ids,
    ).exclude(status__in=["cancelled", "completed"])

    if batch_size is not None:
        affected_procedures = (
            affected_procedures
            .exclude(status="attention_needed")
            .order_by("pk")[:batch_size]
        )

    for procedure in affected_procedures:
        if procedure.status != "attention_needed":
            _mark_procedure_attention_needed(procedure)

    # Reconcile preparation progress for procedures that still
    # have an eligible status. Preserve terminal and attention states.
    eligible_procedures = Procedure.objects.exclude(
        status__in=["cancelled", "completed", "attention_needed"]
    ).filter(
        reminders__isnull=False,
    ).distinct()

    if batch_size is not None:
        procedure_reminders = Reminder.objects.filter(
            procedure_id=models.OuterRef("pk"),
        )

        eligible_procedures = (
            eligible_procedures.annotate(
                has_unconfirmed=models.Exists(
                    procedure_reminders.exclude(
                        status="confirmed",
                    )
                ),
                has_missed_critical=models.Exists(
                    procedure_reminders.filter(
                        status="missed",
                        prep_step__is_critical=True,
                    )
                ),
            )
            .filter(
                models.Q(has_missed_critical=True)
                | (
                    models.Q(
                        has_missed_critical=False,
                        has_unconfirmed=True,
                    )
                    & ~models.Q(status="prep_in_progress")
                )
                | (
                    models.Q(
                        has_missed_critical=False,
                        has_unconfirmed=False,
                    )
                    & ~models.Q(status="ready")
                )
            )
            .order_by("pk")[:batch_size]
        )

    for procedure in eligible_procedures:
        sync_procedure_status(procedure)

    # Legacy Celery execution retains notification delivery.
    # Bounded HTTPS reconciliation must not perform unbounded
    # external network operations.
    if batch_size is None:
        _send_pending_missed_reminder_alerts()
        _send_pending_missed_reminder_whatsapp_alerts()

@shared_task
def process_single_test_reminder(reminder_id):
    """
    Safely test one reminder without processing other due reminders.
    Uses the patient's saved phone number and respects the WhatsApp guard.
    """
    from django.conf import settings

    if not settings.WHATSAPP_SEND_ENABLED:
        logger.warning(
            "Test reminder %s was not processed: WhatsApp sending is disabled.",
            reminder_id,
        )
        return {
            "success": False,
            "reason": "whatsapp_sending_disabled",
            "reminder_id": reminder_id,
        }

    reminder = _claim_reminder(reminder_id, timezone.now())

    if reminder is None:
        return {
            "success": False,
            "reason": "reminder_not_eligible",
            "reminder_id": reminder_id,
        }

    try:

        from .whatsapp import send_whatsapp_template

        result = send_whatsapp_template(
            phone_number=reminder.procedure.patient.phone_number,
            patient_name="PrepBuddy test",
            procedure_name="Connectivity test",
            preparation_step="Test message only",
            instructions=(
                "This is a PrepBuddy connectivity test. "
                "No medical action is required."
            ),
            dedupe_key=f"reminder:{reminder.pk}:test",
            purpose="test_reminder",
        )

        if isinstance(result, dict) and result:
            message_id = result.get("messageId")
            success_updates = {
                "status": "sent",
                "sent_at": timezone.now(),
                "next_attempt_at": None,
                "delivery_status": "accepted" if message_id else "unknown",
            }
            if message_id:
                success_updates["openwa_message_id"] = str(message_id)

            updated = _update_claimed_reminder(
                reminder,
                **success_updates,
            )

            if not updated:
                return {
                    "success": False,
                    "reason": "claim_lost",
                    "reminder_id": reminder.id,
                }

            return {
                "success": True,
                "reminder_id": reminder.id,
                "status": reminder.status,
                "delivery_status": reminder.delivery_status,
            }

        _schedule_retry(reminder)
        return {
            "success": False,
            "reason": "empty_or_invalid_response",
            "reminder_id": reminder.id,
            "status": reminder.status,
        }

    except Exception:
        _schedule_retry(reminder)
        logger.exception(
            "Single test reminder %s failed on attempt %s.",
            reminder.id,
            reminder.delivery_attempts,
        )
        return {
            "success": False,
            "reason": "delivery_exception",
            "reminder_id": reminder.id,
            "status": reminder.status,
        }

@shared_task
def scheduler_heartbeat():
    """Harmless task to verify Celery Beat scheduling."""
    logger.info("PrepBuddy scheduler heartbeat executed successfully.")
    return {
        "success": True,
        "task": "scheduler_heartbeat",
    }
