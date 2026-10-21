
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import IntegrityError, transaction
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from .models import Patient


def patient_to_dict(patient):
    return {
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
    }


@require_http_methods(["GET", "POST"])
def patients_list(request):
    if request.method == "GET":
        patients = Patient.objects.all().order_by(
            "first_name", "last_name"
        )
        return JsonResponse({
            "patients": [patient_to_dict(p) for p in patients]
        })

    import json

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

    first_name = payload.get("first_name", "").strip()
    last_name = payload.get("last_name", "").strip()
    phone_number = payload.get("phone_number", "").strip()
    email = payload.get("email", "").strip()

    errors = {}

    if not first_name:
        errors["first_name"] = "First name is required."
    if not last_name:
        errors["last_name"] = "Last name is required."
    if not phone_number:
        errors["phone_number"] = "Phone number is required."
    elif len(phone_number) > 20:
        errors["phone_number"] = "Phone number must be 20 characters or fewer."

    if email:
        try:
            validate_email(email)
        except ValidationError:
            errors["email"] = "Enter a valid email address."

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    if Patient.objects.filter(phone_number=phone_number).exists():
        return JsonResponse(
            {"errors": {
                "phone_number": "A patient with this phone number already exists."
            }},
            status=409,
        )

    try:
        with transaction.atomic():
            patient = Patient.objects.create(
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                email=email,
            )
    except IntegrityError:
        # Handles a duplicate phone number submitted concurrently.
        return JsonResponse(
            {"errors": {
                "phone_number": "A patient with this phone number already exists."
            }},
            status=409,
        )

    return JsonResponse(
        {"patient": patient_to_dict(patient)},
        status=201,
    )


from django.views.decorators.http import require_http_methods


@require_http_methods(["DELETE"])
def delete_patient_api(request, patient_id):
    # Only authenticated clinic staff or doctors may delete patients.
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Please log in to delete patients."},
            status=401,
        )

    profile = getattr(request.user, "staff_profile", None)
    if profile is None or profile.role not in {"clinic_staff", "doctor"}:
        return JsonResponse(
            {"error": "You are not authorized to delete patients."},
            status=403,
        )

    patient = Patient.objects.filter(pk=patient_id).first()

    if patient is None:
        return JsonResponse(
            {"error": "Patient not found."},
            status=404,
        )

    # Preserve procedures, reminders, and their clinical history.
    if patient.procedures.exists():
        return JsonResponse(
            {
                "error": (
                    "This patient has associated procedures. "
                    "Resolve or archive those records before deleting "
                    "the patient."
                )
            },
            status=409,
        )

    patient.delete()

    return JsonResponse(
        {"message": "Patient deleted successfully."},
        status=200,
    )
