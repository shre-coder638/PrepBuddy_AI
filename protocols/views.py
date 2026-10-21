
import json

from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from reminders.models import Reminder
from .models import PrepProtocol, PrepStep


def protocol_to_dict(protocol):
    steps = list(protocol.steps.all())

    return {
        "id": protocol.id,
        "name": protocol.name,
        "description": protocol.description,
        "is_active": protocol.is_active,
        "step_count": len(steps),
        "steps": [
            {
                "id": step.id,
                "title": step.title,
                "instruction": step.instruction,
                "minutes_before_procedure": step.minutes_before_procedure,
                "requires_confirmation": step.requires_confirmation,
                "is_critical": step.is_critical,
                "order": step.order,
            }
            for step in steps
        ],
    }


@require_http_methods(["GET", "POST", "DELETE"])
def protocol_list(request):
    
    if request.method == "DELETE":
        if not request.user.is_authenticated:
            return JsonResponse(
                {"error": "Please log in to delete protocols."},
                status=401,
            )

        profile = getattr(request.user, "staff_profile", None)
        if profile is None or profile.role not in {"clinic_staff", "doctor"}:
            return JsonResponse(
                {"error": "You are not authorized to delete protocols."},
                status=403,
            )

        protocol_id = request.GET.get("id")
        if not protocol_id or not protocol_id.isdigit():
            return JsonResponse(
                {"error": "A valid protocol ID is required."},
                status=400,
            )

        protocol = PrepProtocol.objects.filter(pk=int(protocol_id)).first()
        if protocol is None:
            return JsonResponse(
                {"error": "Protocol not found."},
                status=404,
            )

        if protocol.procedures.exists():
            return JsonResponse(
                {
                    "error": (
                        "This protocol is linked to existing procedures. "
                        "Deactivate it instead to preserve clinical history."
                    )
                },
                status=409,
            )

        if Reminder.objects.filter(
            prep_step__protocol=protocol
        ).exists():
            return JsonResponse(
                {
                    "error": (
                        "This protocol has preparation steps referenced by "
                        "reminders. It cannot be deleted."
                    )
                },
                status=409,
            )

        try:
            protocol.delete()
        except Exception:
            return JsonResponse(
                {
                    "error": (
                        "The protocol could not be deleted because related "
                        "records require it to be preserved."
                    )
                },
                status=409,
            )

        return JsonResponse(
            {"message": "Protocol deleted successfully."},
            status=200,
        )

    if request.method == "GET":
        protocols = (
            PrepProtocol.objects
            .prefetch_related("steps")
            .order_by("name")
        )

        return JsonResponse({
            "protocols": [protocol_to_dict(p) for p in protocols]
        })

    try:
        payload = json.loads(request.body or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "Request body must contain valid JSON."},
            status=400,
        )

    if not isinstance(payload, dict):
        return JsonResponse(
            {"error": "Request body must be a JSON object."},
            status=400,
        )

    name = payload.get("name")
    description = payload.get("description", "")
    steps = payload.get("steps", [])
    is_active = payload.get("is_active", True)

    errors = {}

    if not isinstance(name, str) or not name.strip():
        errors["name"] = "Protocol name is required."
    elif len(name.strip()) > 200:
        errors["name"] = "Protocol name must be 200 characters or fewer."

    if not isinstance(description, str):
        errors["description"] = "Description must be text."

    if not isinstance(is_active, bool):
        errors["is_active"] = "Active status must be true or false."

    if not isinstance(steps, list) or not steps:
        errors["steps"] = "Add at least one preparation step."
    else:
        for index, step in enumerate(steps):
            prefix = f"steps.{index}"

            if not isinstance(step, dict):
                errors[prefix] = "Each step must be an object."
                continue

            title = step.get("title")
            instruction = step.get("instruction")
            minutes = step.get("minutes_before_procedure")
            requires_confirmation = step.get("requires_confirmation", True)
            is_critical = step.get("is_critical", False)
            order = step.get("order", index)

            if not isinstance(title, str) or not title.strip():
                errors[f"{prefix}.title"] = "Step title is required."
            elif len(title.strip()) > 200:
                errors[f"{prefix}.title"] = (
                    "Step title must be 200 characters or fewer."
                )

            if not isinstance(instruction, str) or not instruction.strip():
                errors[f"{prefix}.instruction"] = (
                    "Step instruction is required."
                )

            if (
                isinstance(minutes, bool)
                or not isinstance(minutes, int)
                or minutes < 0
            ):
                errors[f"{prefix}.minutes_before_procedure"] = (
                    "Timing must be a non-negative whole number of minutes."
                )

            if not isinstance(requires_confirmation, bool):
                errors[f"{prefix}.requires_confirmation"] = (
                    "Confirmation setting must be true or false."
                )

            if not isinstance(is_critical, bool):
                errors[f"{prefix}.is_critical"] = (
                    "Critical setting must be true or false."
                )

            if (
                isinstance(order, bool)
                or not isinstance(order, int)
                or order < 0
            ):
                errors[f"{prefix}.order"] = (
                    "Step order must be a non-negative whole number."
                )

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    try:
        with transaction.atomic():
            protocol = PrepProtocol.objects.create(
                name=name.strip(),
                description=description.strip(),
                is_active=is_active,
            )

            for index, step in enumerate(steps):
                PrepStep.objects.create(
                    protocol=protocol,
                    title=step["title"].strip(),
                    instruction=step["instruction"].strip(),
                    minutes_before_procedure=(
                        step["minutes_before_procedure"]
                    ),
                    requires_confirmation=step.get(
                        "requires_confirmation", True
                    ),
                    is_critical=step.get("is_critical", False),
                    order=step.get("order", index),
                )

            protocol = (
                PrepProtocol.objects
                .prefetch_related("steps")
                .get(pk=protocol.pk)
            )

    except IntegrityError:
        return JsonResponse(
            {"error": "The protocol could not be saved."},
            status=400,
        )

    return JsonResponse(
        {"protocol": protocol_to_dict(protocol)},
        status=201,
    )
