from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from reminders.models import Reminder
from .services import send_reminder


@shared_task
def process_due_reminders():
    now = timezone.now()

    reminders = Reminder.objects.filter(
        status="pending",
        scheduled_at__lte=now,
    )

    for reminder in reminders:
        success = send_reminder(reminder)

        if success:
            reminder.status = "sent"
            reminder.sent_at = timezone.now()

            reminder.save(
                update_fields=[
                    "status",
                    "sent_at",
                ]
            )


@shared_task
def check_missed_reminders():
    now = timezone.now()
    cutoff = now - timedelta(hours=2)

    reminders = Reminder.objects.filter(
        status="sent",
        sent_at__lte=cutoff,
    )

    for reminder in reminders:
        reminder.status = "missed"

        reminder.save(
            update_fields=["status"]
        )

        if reminder.prep_step.is_critical:
            procedure = reminder.procedure

            procedure.status = "attention_needed"

            procedure.save(
                update_fields=["status"]
            )

            print(
                f"🚨 CRITICAL PREP FAILURE: "
                f"Procedure #{procedure.id}"
            )