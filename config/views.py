from django.shortcuts import render
from django.utils import timezone

from patients.models import Patient
from procedures.models import Procedure
from reminders.models import Reminder


def dashboard(request):
    now = timezone.now()

    upcoming_procedures = (
        Procedure.objects
        .filter(scheduled_at__gte=now)
        .exclude(status="cancelled")
        .select_related("patient", "protocol")
        .order_by("scheduled_at")[:6]
    )

    recent_reminders = (
        Reminder.objects
        .select_related("procedure__patient", "prep_step")
        .order_by("-created_at")[:8]
    )

    attention_needed_procedures = (
        Procedure.objects
        .filter(status="attention_needed")
        .select_related("patient", "protocol")
        .order_by("-updated_at")
    )

    return render(
        request,
        "dashboard.html",
        {
            "now": now,

            "stats": {
                "patients": Patient.objects.count(),

                "upcoming_procedures": (
                    Procedure.objects
                    .filter(scheduled_at__gte=now)
                    .exclude(status="cancelled")
                    .count()
                ),

                "pending_reminders": Reminder.objects.filter(
                    status="pending"
                ).count(),

                "confirmed_reminders": Reminder.objects.filter(
                    status="confirmed"
                ).count(),

                "attention_needed": Procedure.objects.filter(
                    status="attention_needed"
                ).count(),
            },

            "upcoming_procedures": upcoming_procedures,
            "recent_reminders": recent_reminders,
            "attention_needed_procedures": attention_needed_procedures,
        },
    )


def privacy_policy(request):
    return render(request, "privacy_policy.html")