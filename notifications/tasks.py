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
            .update(delivery_attempts=F("delivery_attempts") + 1)
        )

        if updated != 1:
            return None

        return Reminder.objects.select_related(
            "procedure__patient",
            "prep_step",
        ).get(id=reminder_id)

@shared_task
def process_due_reminders():
    now = timezone.now()

    stale_cutoff = now - timedelta(hours=2)

    due_ids = list(
        Reminder.objects.filter(
            status="pending",
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

    for reminder_id in due_ids:
        reminder = _claim_reminder(reminder_id, timezone.now())

        # Another worker may already have claimed or changed it.
        if reminder is None:
            continue

        try:
            result = send_reminder(reminder)

            if isinstance(result, dict) and result:
                reminder.status = "sent"
                reminder.sent_at = timezone.now()
                reminder.next_attempt_at = None

                message_id = result.get("messageId")
                if message_id:
                    reminder.openwa_message_id = str(message_id)
                    reminder.delivery_status = "accepted"
                else:
                    reminder.delivery_status = "unknown"
                    logger.warning(
                        "OpenWA accepted reminder %s but returned no messageId; "
                        "delivery acknowledgements cannot be matched reliably.",
                        reminder.id,
                    )

                reminder.save(
                    update_fields=[
                        "status",
                        "sent_at",
                        "next_attempt_at",
                        "openwa_message_id",
                        "delivery_status",
                    ]
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
        reminder.status = "failed"
        reminder.next_attempt_at = None
        logger.error(
            "Reminder %s exhausted its delivery attempts.",
            reminder.id,
        )
    else:
        delay_minutes = RETRY_DELAYS_MINUTES.get(
            reminder.delivery_attempts,
            15,
        )
        reminder.next_attempt_at = (
            timezone.now() + timedelta(minutes=delay_minutes)
        )

    reminder.save(
        update_fields=["status", "next_attempt_at"]
    )

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
    """Email staff about alerts that have not been successfully sent."""
    alerts = MissedReminderAlert.objects.filter(
        email_sent_at__isnull=True,
    ).select_related(
        "reminder__procedure",
    )

    for alert in alerts:
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
            alert.last_error = "No active staff email recipients configured."
            alert.save(update_fields=["last_error"])
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
                alert.email_sent_at = timezone.now()
                alert.last_error = ""
                alert.save(
                    update_fields=["email_sent_at", "last_error"],
                )
                logger.info(
                    "Staff alert email sent for missed reminder %s.",
                    reminder.id,
                )
            else:
                alert.last_error = "Email backend did not confirm a sent message."
                alert.save(update_fields=["last_error"])
                logger.warning(
                    "Staff alert email was not confirmed for reminder %s.",
                    reminder.id,
                )

        except Exception as exc:
            alert.last_error = str(exc)[:2000]
            alert.save(update_fields=["last_error"])
            logger.exception(
                "Failed to email staff about missed reminder %s.",
                reminder.id,
            )

def _send_pending_missed_reminder_whatsapp_alerts():
    """Send pending missed-reminder alerts to active doctors."""
    alerts = MissedReminderAlert.objects.filter(
        whatsapp_sent_at__isnull=True,
    ).select_related(
        "reminder__procedure",
    )

    doctors = list(
        StaffProfile.objects.filter(
            role="doctor",
            user__is_active=True,
        ).exclude(
            phone_number="",
        )
    )

    for alert in alerts:
        if not doctors:
            alert.whatsapp_last_error = (
                "No active doctors with phone numbers are configured."
            )
            alert.save(update_fields=["whatsapp_last_error"])
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
            alert.save(update_fields=["whatsapp_last_error"])
            logger.warning(
                "WhatsApp alert for reminder %s remains pending.",
                reminder.id,
            )
        else:
            alert.whatsapp_sent_at = timezone.now()
            alert.whatsapp_last_error = ""
            alert.save(
                update_fields=[
                    "whatsapp_sent_at",
                    "whatsapp_last_error",
                ]
            )
            logger.info(
                "OpenWA accepted doctor alert for missed reminder %s. "
                "Actual recipient delivery is not confirmed.",
                reminder.id,
            )

@shared_task
def check_missed_reminders():
    now = timezone.now()
    cutoff = now - timedelta(hours=2)

    # Mark sent reminders as missed if they remain unconfirmed.
    reminders = Reminder.objects.filter(
        status="sent",
        sent_at__lte=cutoff,
    ).select_related("prep_step", "procedure")

    for reminder in reminders:
        reminder.status = "missed"
        reminder.save(update_fields=["status"])
        _queue_missed_reminder_alert(reminder)

        if reminder.prep_step.is_critical:
            procedure = reminder.procedure

            if procedure.status not in ["cancelled", "completed"]:
                procedure.status = "attention_needed"
                procedure.save(update_fields=["status", "updated_at"])

                print(
                    f"CRITICAL PREP FAILURE: "
                    f"Procedure #{procedure.id}"
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

    for reminder in overdue_pending:
        reminder.status = "missed"
        reminder.next_attempt_at = None
        reminder.save(
            update_fields=["status", "next_attempt_at"]
        )
        _queue_missed_reminder_alert(reminder)

        if reminder.prep_step.is_critical:
            procedure = reminder.procedure

            if procedure.status != "attention_needed":
                procedure.status = "attention_needed"
                procedure.save(
                    update_fields=["status", "updated_at"]
                )

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

    for procedure in affected_procedures:
        if procedure.status != "attention_needed":
            procedure.status = "attention_needed"
            procedure.save(update_fields=["status", "updated_at"])

    # Reconcile preparation progress for procedures that still
    # have an eligible status. Preserve terminal and attention states.
    eligible_procedures = Procedure.objects.exclude(
        status__in=["cancelled", "completed", "attention_needed"]
    ).filter(
        reminders__isnull=False,
    ).distinct()

    for procedure in eligible_procedures:
        sync_procedure_status(procedure)

    # Retry pending staff email alerts.
    _send_pending_missed_reminder_alerts()

    # Retry pending doctor WhatsApp alerts.
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
        )

        if isinstance(result, dict) and result:
            reminder.status = "sent"
            reminder.sent_at = timezone.now()
            reminder.next_attempt_at = None

            message_id = result.get("messageId")
            if message_id:
                reminder.openwa_message_id = str(message_id)
                reminder.delivery_status = "accepted"
            else:
                reminder.delivery_status = "unknown"

            reminder.save(
                update_fields=[
                    "status",
                    "sent_at",
                    "next_attempt_at",
                    "openwa_message_id",
                    "delivery_status",
                ]
            )

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
