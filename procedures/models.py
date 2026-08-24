from django.db import models
from patients.models import Patient
from protocols.models import PrepProtocol


class Procedure(models.Model):

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("prep_in_progress", "Prep In Progress"),
        ("ready", "Ready"),
        ("attention_needed", "Attention Needed"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    ]

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="procedures"
    )

    protocol = models.ForeignKey(
        PrepProtocol,
        on_delete=models.PROTECT,
        related_name="procedures"
    )

    procedure_name = models.CharField(max_length=200)

    scheduled_at = models.DateTimeField()

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="scheduled"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.procedure_name} - {self.patient}"