
from django.db import models

class WhatsAppAssistantSession(models.Model):
    patient = models.OneToOneField(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="whatsapp_assistant_session",
    )
    is_active = models.BooleanField(default=False)
    activated_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"{self.patient} - WhatsApp assistant {status}"

class WhatsAppConversationMessage(models.Model):
    ROLE_CHOICES = [
        ("patient", "Patient"),
        ("assistant", "Assistant"),
    ]

    session = models.ForeignKey(
        WhatsAppAssistantSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.session.patient_id} - {self.role} - {self.created_at}"

class ProcessedWhatsAppMessage(models.Model):
    message_id = models.CharField(max_length=255, unique=True)
    is_processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    def __str__(self):
        status = "processed" if self.is_processed else "pending"
        return f"{self.message_id} - {status}"

class MissedReminderAlert(models.Model):
    """One persistent staff alert per missed reminder."""

    whatsapp_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    whatsapp_last_error = models.TextField(
        blank=True,
        default="",
    )

    reminder = models.OneToOneField(
        "reminders.Reminder",
        on_delete=models.CASCADE,
        related_name="staff_alert",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    last_error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Staff alert for reminder {self.reminder_id}"
