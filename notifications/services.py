from reminders.models import Reminder

from .whatsapp import send_whatsapp_template


def send_reminder(reminder: Reminder):
    patient = reminder.procedure.patient
    step = reminder.prep_step
    procedure = reminder.procedure

    send_whatsapp_template(
        phone_number=patient.phone_number,
        patient_name=patient.first_name,
        procedure_name=procedure.procedure_name,
        preparation_step=step.title,
        instructions=step.instruction,
    )

    return True