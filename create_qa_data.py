from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from patients.models import Patient
from protocols.models import PrepProtocol, PrepStep
from reminders.models import Reminder

Procedure = Reminder._meta.get_field("procedure").related_model

with transaction.atomic():
    patient = Patient.objects.get(pk=8)
    if not str(patient.phone_number).strip().endswith("2321"):
        raise ValueError("Patient verification failed")

    protocol, created = PrepProtocol.objects.get_or_create(
        name="PrepBuddy QA - Non-clinical test only",
        defaults={
            "description": "Synthetic QA data only. Not a clinical protocol.",
            "is_active": True,
        },
    )
    if not protocol.is_active:
        raise ValueError("QA protocol is inactive")

    instruction = (
        "TEST ONLY: This is not a medical instruction. "
        "No preparation action is required. "
        "Contact your clinical team for all real procedure instructions."
    )

    step, step_created = PrepStep.objects.get_or_create(
        protocol=protocol,
        title="Read the test notice",
        defaults={
            "instruction": instruction,
            "minutes_before_procedure": 1440,
            "requires_confirmation": False,
            "is_critical": False,
            "order": 0,
        },
    )
    if step.instruction != instruction:
        raise ValueError("Existing QA instruction does not match")

    procedure, procedure_created = Procedure.objects.get_or_create(
        patient=patient,
        protocol=protocol,
        procedure_name="PrepBuddy Integration Test - Not a real procedure",
        defaults={
            "scheduled_at": timezone.now() + timedelta(days=1),
            "status": "scheduled",
        },
    )
    if procedure.status != "scheduled" or procedure.scheduled_at <= timezone.now():
        raise ValueError("QA procedure is not safely future-scheduled")

    print("Patient ID:", patient.pk)
    print("Protocol ID:", protocol.pk, "created:", created)
    print("Step ID:", step.pk, "created:", step_created)
    print("Procedure ID:", procedure.pk, "created:", procedure_created)
    print("Procedure status:", procedure.status)
    print("Instruction:", step.instruction)
