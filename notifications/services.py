from reminders.models import Reminder

from .whatsapp import send_whatsapp_template


def send_reminder(reminder: Reminder):
    patient = reminder.procedure.patient
    procedure = reminder.procedure
    step = reminder.prep_step

    response = send_whatsapp_template(
        phone_number=patient.phone_number,
        patient_name=patient.first_name,
        procedure_name=procedure.procedure_name,
        preparation_step=step.title,
        instructions=step.instruction,
    )

    print("=" * 60)
    print("📱 PREPBUDDY REMINDER SENT")
    print("=" * 60)
    print(f"Patient     : {patient}")
    print(f"Phone       : {patient.phone_number}")
    print(f"Procedure   : {procedure.procedure_name}")
    print(f"Step        : {step.title}")
    print(f"Response    : {response}")
    print("=" * 60)

    return True