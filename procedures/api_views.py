
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from reminders.models import Reminder

from .models import Procedure


@require_GET
def procedures_list(request):
    procedures = (
        Procedure.objects
        .select_related("patient")
        .order_by("-scheduled_at")
    )

    data = []

    for procedure in procedures:
        data.append({
            "id": procedure.id,
            "patient": {
                "id": procedure.patient.id,
                "first_name": procedure.patient.first_name,
                "last_name": procedure.patient.last_name,
            },
            "procedure_name": procedure.procedure_name,
            "scheduled_at": procedure.scheduled_at.isoformat(),
            "status": procedure.status,
        })

    return JsonResponse({"procedures": data})


@require_GET
def procedure_timeline(request, procedure_id):
    procedure = get_object_or_404(
        Procedure.objects.select_related("patient", "protocol"),
        id=procedure_id,
    )

    steps = procedure.protocol.steps.all()
    timeline = []

    for step in steps:
        reminder = (
            Reminder.objects
            .filter(
                procedure=procedure,
                prep_step=step,
            )
            .order_by("-scheduled_at")
            .first()
        )

        timeline.append({
            "step_id": step.id,
            "title": step.title,
            "instruction": step.instruction,
            "order": step.order,
            "minutes_before_procedure": step.minutes_before_procedure,
            "is_critical": step.is_critical,
            "requires_confirmation": step.requires_confirmation,
            "reminder": (
                {
                    "id": reminder.id,
                    "scheduled_at": reminder.scheduled_at.isoformat(),
                    "sent_at": (
                        reminder.sent_at.isoformat()
                        if reminder.sent_at
                        else None
                    ),
                    "confirmed_at": (
                        reminder.confirmed_at.isoformat()
                        if reminder.confirmed_at
                        else None
                    ),
                    "status": reminder.status,
                    "delivery_attempts": reminder.delivery_attempts,
                }
                if reminder
                else None
            ),
        })

    return JsonResponse({
        "procedure": {
            "id": procedure.id,
            "procedure_name": procedure.procedure_name,
            "scheduled_at": procedure.scheduled_at.isoformat(),
            "status": procedure.status,
            "patient": {
                "id": procedure.patient.id,
                "first_name": procedure.patient.first_name,
                "last_name": procedure.patient.last_name,
            },
        },
        "timeline": timeline,
    })
