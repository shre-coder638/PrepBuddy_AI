from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import authentication_classes

from procedures.models import Procedure
from .models import Reminder

from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import permission_classes
from .models import Reminder, ReminderFollowUp


def sync_procedure_status(procedure):
    """
    Synchronize procedure status with preparation reminder progress.
    Never overwrite terminal or attention-needed statuses.
    """
    if procedure.status in [
        "cancelled",
        "completed",
        "attention_needed",
    ]:
        return

    has_missed_critical = Reminder.objects.filter(
        procedure=procedure,
        status="missed",
        prep_step__is_critical=True,
    ).exists()

    if has_missed_critical:
        procedure.status = "attention_needed"
    elif not procedure.reminders.exists():
        return
    elif procedure.reminders.exclude(status="confirmed").exists():
        procedure.status = "prep_in_progress"
    else:
        procedure.status = "ready"

    procedure.save(update_fields=["status", "updated_at"])


@api_view(["POST"])
def confirm_reminder(request, token):
    with transaction.atomic():
        reminder = get_object_or_404(
            Reminder.objects.select_for_update(),
            confirmation_token=token,
        )

        procedure = Procedure.objects.select_for_update().get(
            pk=reminder.procedure_id
        )

        if reminder.status == "confirmed":
            # Also repairs existing records whose reminder was confirmed
            # before procedure-status synchronization was implemented.
            sync_procedure_status(procedure)

            return Response({
                "message": "This preparation step is already confirmed.",
                "status": reminder.status,
                "confirmed_at": reminder.confirmed_at,
                "procedure_status": procedure.status,
            })

        if reminder.status in ["cancelled", "missed"]:
            return Response(
                {
                    "error": (
                        "This preparation step can no longer be confirmed."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        reminder.status = "confirmed"
        reminder.confirmed_at = timezone.now()
        reminder.save(update_fields=["status", "confirmed_at"])

        sync_procedure_status(procedure)

        return Response({
            "message": "Preparation step confirmed successfully.",
            "status": reminder.status,
            "confirmed_at": reminder.confirmed_at,
            "procedure_status": procedure.status,
        })


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
@csrf_protect
def create_reminder_follow_up(request):
    profile = getattr(request.user, "staff_profile", None)

    if profile is None or profile.role not in {
        "clinic_staff",
        "doctor",
    }:
        return Response(
            {"error": "You are not authorized to record staff follow-ups."},
            status=status.HTTP_403_FORBIDDEN,
        )

    allowed_contact_outcomes = {
        "reached",
        "unreachable",
        "escalated",
    }
    allowed_preparation_statuses = {
        "completed",
        "not_completed",
        "unknown",
    }

    reminder_id = request.data.get("reminder_id")
    contact_outcome = request.data.get("contact_outcome")
    preparation_status = request.data.get(
        "preparation_status",
        "unknown",
    )
    notes = request.data.get("notes", "")

    if not reminder_id:
        return Response(
            {"error": "reminder_id is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if contact_outcome not in allowed_contact_outcomes:
        return Response(
            {"error": "Invalid contact_outcome."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if preparation_status not in allowed_preparation_statuses:
        return Response(
            {"error": "Invalid preparation_status."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not isinstance(notes, str):
        return Response(
            {"error": "notes must be a string."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        reminder = get_object_or_404(
            Reminder.objects.select_for_update(),
            pk=reminder_id,
        )

        if reminder.status != "missed":
            return Response(
                {"error": "Follow-up can only be recorded for missed reminders."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        follow_up = ReminderFollowUp.objects.create(
            reminder=reminder,
            contact_outcome=contact_outcome,
            preparation_status=preparation_status,
            notes=notes.strip(),
            requires_clinical_review=True,
            created_by=request.user,
        )

    return Response(
        {
            "message": "Staff follow-up recorded.",
            "follow_up": {
                "id": follow_up.id,
                "reminder_id": follow_up.reminder_id,
                "contact_outcome": follow_up.contact_outcome,
                "preparation_status": follow_up.preparation_status,
                "notes": follow_up.notes,
                "requires_clinical_review": follow_up.requires_clinical_review,
                "created_by": request.user.get_username(),
                "created_at": follow_up.created_at.isoformat(),
            },
            "reminder_status": reminder.status,
        },
        status=status.HTTP_201_CREATED,
    )
