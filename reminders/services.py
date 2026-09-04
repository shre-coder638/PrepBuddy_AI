from datetime import timedelta

from django.db import transaction

from .models import Reminder


@transaction.atomic
def generate_reminders_for_procedure(procedure):
    """
    Generate reminders for all prep steps associated
    with a procedure's protocol.
    """

    # Prevent duplicate reminders
    if procedure.reminders.exists():
        return list(procedure.reminders.all())

    reminders = []

    steps = procedure.protocol.steps.all()

    for step in steps:
        scheduled_at = (
            procedure.scheduled_at
            - timedelta(minutes=step.minutes_before_procedure)
        )

        reminder = Reminder.objects.create(
            procedure=procedure,
            prep_step=step,
            scheduled_at=scheduled_at,
        )

        reminders.append(reminder)

    return reminders