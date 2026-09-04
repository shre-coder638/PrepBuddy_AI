import secrets

from django.db import models
from procedures.models import Procedure
from protocols.models import PrepStep


class Reminder(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("confirmed", "Confirmed"),
        ("missed", "Missed"),
        ("cancelled", "Cancelled"),
    ]

    procedure = models.ForeignKey(
        Procedure,
        on_delete=models.CASCADE,
        related_name="reminders"
    )

    prep_step = models.ForeignKey(
        PrepStep,
        on_delete=models.PROTECT,
        related_name="reminders"
    )

    scheduled_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    confirmation_token = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.procedure.patient} - {self.prep_step.title}"