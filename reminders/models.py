import secrets

from django.db import models
from procedures.models import Procedure
from protocols.models import PrepStep
from django.conf import settings

class Reminder(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("confirmed", "Confirmed"),
        ("missed", "Missed"),
        ("cancelled", "Cancelled"),
        ("failed", "Failed"),
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
    next_attempt_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    sent_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    
    # OpenWA message tracking
    openwa_message_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
    )
    
    delivery_status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "Pending"),
            ("accepted", "Accepted by OpenWA"),
            ("sent", "Sent"),
            ("delivered", "Delivered"),
            ("read", "Read"),
            ("failed", "Failed"),
            ("unknown", "Unknown"),
        ],
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    delivery_attempts = models.PositiveSmallIntegerField(default=0)

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
    def save(self, *args, **kwargs):
        if not self.confirmation_token:
            self.confirmation_token = secrets.token_urlsafe(32)

        super().save(*args, **kwargs)



class ReminderFollowUp(models.Model):
    CONTACT_OUTCOME_CHOICES = [
        ("reached", "Patient contacted"),
        ("unreachable", "Patient could not be reached"),
        ("escalated", "Escalated to clinical staff"),
    ]

    PREPARATION_STATUS_CHOICES = [
        ("completed", "Patient reports completed"),
        ("not_completed", "Patient reports not completed"),
        ("unknown", "Not yet verified"),
    ]

    reminder = models.ForeignKey(
        Reminder,
        on_delete=models.PROTECT,
        related_name="follow_ups",
    )

    contact_outcome = models.CharField(
        max_length=20,
        choices=CONTACT_OUTCOME_CHOICES,
    )

    preparation_status = models.CharField(
        max_length=20,
        choices=PREPARATION_STATUS_CHOICES,
        default="unknown",
    )

    notes = models.TextField(blank=True)

    requires_clinical_review = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reminder_follow_ups",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Follow-up for reminder {self.reminder_id} "
            f"by {self.created_by}"
        )
