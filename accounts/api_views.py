
import json

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from .models import DoctorProfile

from django.contrib.auth.decorators import login_required

from .models import DoctorProfile


@login_required
@ensure_csrf_cookie
@require_http_methods(["GET", "PUT"])
def doctor_profile_api(request):
    user = request.user
    staff_profile = getattr(user, "staff_profile", None)
    phone_number = staff_profile.phone_number if staff_profile else ""

    profile, created = DoctorProfile.objects.get_or_create(
        user=user,
        defaults={
            "full_name": user.get_full_name() or user.username,
            "professional_role": "Clinic Staff",
            "specialty": "",
            "email": user.email or "",
            "phone": phone_number,
        },
    )

    if request.method == "GET":
        return JsonResponse({
            "full_name": profile.full_name,
            "professional_role": profile.professional_role,
            "specialty": profile.specialty,
            "email": profile.email,
            "phone": profile.phone,
        })

    try:
        data = json.loads(request.body or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    allowed_fields = [
        "full_name",
        "professional_role",
        "specialty",
        "email",
        "phone",
    ]

    for field in allowed_fields:
        if field in data:
            value = data[field]

            if not isinstance(value, str):
                return JsonResponse(
                    {"error": f"{field} must be a string."},
                    status=400,
                )

            setattr(profile, field, value)

    profile.save()

    return JsonResponse({
        "message": "Doctor profile saved successfully.",
        "full_name": profile.full_name,
        "professional_role": profile.professional_role,
        "specialty": profile.specialty,
        "email": profile.email,
        "phone": profile.phone,
    })


from .models import UserSettings


@require_http_methods(["GET", "PUT"])
def user_settings_api(request):
    User = get_user_model()
    user = User.objects.order_by("id").first()

    if user is None:
        return JsonResponse(
            {"error": "No Django user exists. Create a user first."},
            status=404,
        )

    settings_obj, _ = UserSettings.objects.get_or_create(user=user)

    if request.method == "GET":
        return JsonResponse({
            "notifications_enabled": settings_obj.notifications_enabled,
            "refresh_interval": settings_obj.refresh_interval,
            "retry_attempts": settings_obj.retry_attempts,
        })

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    notifications_enabled = data.get(
        "notifications_enabled",
        settings_obj.notifications_enabled,
    )
    refresh_interval = data.get(
        "refresh_interval",
        settings_obj.refresh_interval,
    )
    retry_attempts = data.get(
        "retry_attempts",
        settings_obj.retry_attempts,
    )

    if not isinstance(notifications_enabled, bool):
        return JsonResponse(
            {"error": "notifications_enabled must be true or false."},
            status=400,
        )

    # Reject booleans as integers and reject invalid numeric values.
    if type(refresh_interval) is not int or refresh_interval not in (10, 30, 60):
        return JsonResponse(
            {"error": "refresh_interval must be 10, 30, or 60."},
            status=400,
        )

    if type(retry_attempts) is not int or retry_attempts not in (1, 2, 3):
        return JsonResponse(
            {"error": "retry_attempts must be 1, 2, or 3."},
            status=400,
        )

    settings_obj.notifications_enabled = notifications_enabled
    settings_obj.refresh_interval = refresh_interval
    settings_obj.retry_attempts = retry_attempts
    settings_obj.save()

    return JsonResponse({
        "message": "Settings saved successfully.",
        "notifications_enabled": settings_obj.notifications_enabled,
        "refresh_interval": settings_obj.refresh_interval,
        "retry_attempts": settings_obj.retry_attempts,
    })
