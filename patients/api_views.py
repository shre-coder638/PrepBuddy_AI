from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import Patient


@require_GET
def patients_list(request):
    patients = Patient.objects.all().order_by("first_name", "last_name")

    data = []

    for patient in patients:
        data.append({
            "id": patient.id,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "phone_number": patient.phone_number,
            "email": patient.email,
            "procedures": [
                {
                    "id": procedure.id,
                    "procedure_name": procedure.procedure_name,
                    "scheduled_at": procedure.scheduled_at.isoformat(),
                    "status": procedure.status,
                }
                for procedure in patient.procedures.all()
            ],
        })

    return JsonResponse({"patients": data})
