
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from reminders.models import Reminder

from .models import Procedure

import json

from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from patients.models import Patient
from protocols.models import PrepProtocol
from reminders.services import generate_reminders_for_procedure


@csrf_exempt
@require_http_methods(["GET", "POST"])
def procedures_list(request):
    if request.method == "POST":
        return create_procedure(request)

    procedures = Procedure.objects.select_related(
        "patient"
    ).order_by("-scheduled_at")

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


@require_http_methods(["DELETE"])
def delete_procedure_api(request, procedure_id):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Please log in to delete procedures."},
            status=401,
        )

    profile = getattr(request.user, "staff_profile", None)
    if profile is None or profile.role not in {"clinic_staff", "doctor"}:
        return JsonResponse(
            {"error": "You are not authorized to delete procedures."},
            status=403,
        )

    procedure = Procedure.objects.filter(pk=procedure_id).first()
    if procedure is None:
        return JsonResponse({"error": "Procedure not found."}, status=404)

    # Preserve clinical follow-up history.
    if Reminder.objects.filter(
        procedure=procedure,
        follow_ups__isnull=False,
    ).exists():
        return JsonResponse(
            {
                "error": (
                    "This procedure has reminder follow-up records. "
                    "It cannot be deleted because clinical history must be preserved."
                )
            },
            status=409,
        )

    try:
        procedure.delete()
    except Exception:
        # Log the exception in production; return a safe message to the client.
        return JsonResponse(
            {
                "error": (
                    "The procedure could not be deleted because related records "
                    "may require it to be preserved."
                )
            },
            status=409,
        )

    return JsonResponse(
        {"message": "Procedure deleted successfully."},
        status=200,
    )


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
                    "confirmation_token": reminder.confirmation_token,
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


@csrf_exempt
@require_http_methods(["POST"])
def create_procedure(request):
    """Create a procedure and its reminders without sending messages."""
    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({"error": "JSON body must be an object"}, status=400)

    patient_id = data.get("patient_id")
    protocol_id = data.get("protocol_id")
    procedure_name = data.get("procedure_name")
    scheduled_at_value = data.get("scheduled_at")

    if not all([patient_id, protocol_id, procedure_name, scheduled_at_value]):
        return JsonResponse({
            "error": "patient_id, protocol_id, procedure_name, and scheduled_at are required"
        }, status=400)

    if not isinstance(procedure_name, str) or not procedure_name.strip():
        return JsonResponse({"error": "procedure_name must be non-empty text"}, status=400)

    if not isinstance(scheduled_at_value, str):
        return JsonResponse({"error": "scheduled_at must be an ISO 8601 datetime"}, status=400)

    scheduled_at = parse_datetime(scheduled_at_value)
    if scheduled_at is None:
        return JsonResponse({"error": "Invalid scheduled_at datetime"}, status=400)

    if timezone.is_naive(scheduled_at):
        return JsonResponse({
            "error": "scheduled_at must include a timezone offset"
        }, status=400)

    patient = Patient.objects.filter(pk=patient_id).first()
    if patient is None:
        return JsonResponse({"error": "Patient not found"}, status=404)

    protocol = PrepProtocol.objects.filter(
        pk=protocol_id,
        is_active=True,
    ).prefetch_related("steps").first()

    if protocol is None:
        return JsonResponse({"error": "Active protocol not found"}, status=404)

    if not protocol.steps.exists():
        return JsonResponse({"error": "Protocol has no preparation steps"}, status=400)

    from .models import Procedure

    with transaction.atomic():
        procedure = Procedure.objects.create(
            patient=patient,
            protocol=protocol,
            procedure_name=procedure_name.strip(),
            scheduled_at=scheduled_at,
        )
        reminders = generate_reminders_for_procedure(procedure)

    return JsonResponse({
        "message": "Procedure created and reminders scheduled.",
        "procedure": {
            "id": procedure.id,
            "patient_id": patient.id,
            "protocol_id": protocol.id,
            "procedure_name": procedure.procedure_name,
            "scheduled_at": procedure.scheduled_at.isoformat(),
            "status": procedure.status,
        },
        "reminders_created": len(reminders),
    }, status=201)
