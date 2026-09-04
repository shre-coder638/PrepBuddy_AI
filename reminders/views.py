from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import Reminder


@api_view(["POST"])
def confirm_reminder(request, token):

    reminder = get_object_or_404(
        Reminder,
        confirmation_token=token
    )

    if reminder.status == "confirmed":
        return Response({
            "message": "This preparation step is already confirmed."
        })

    if reminder.status in ["cancelled", "missed"]:
        return Response(
            {
                "error": "This preparation step can no longer be confirmed."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    reminder.status = "confirmed"
    reminder.confirmed_at = timezone.now()

    reminder.save(
        update_fields=[
            "status",
            "confirmed_at",
        ]
    )

    return Response({
        "message": "Preparation step confirmed successfully.",
        "status": reminder.status,
        "confirmed_at": reminder.confirmed_at,
    })