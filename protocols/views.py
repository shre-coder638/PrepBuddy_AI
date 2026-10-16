from django.http import JsonResponse

from .models import PrepProtocol


def protocol_list(request):
    if request.method != "GET":
        return JsonResponse(
            {"error": "GET request required"},
            status=405,
        )

    protocols = (
        PrepProtocol.objects
        .prefetch_related("steps")
        .order_by("name")
    )

    results = []

    for protocol in protocols:
        steps = protocol.steps.all()

        results.append({
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
        })

    return JsonResponse({"protocols": results})
