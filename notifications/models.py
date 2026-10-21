
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
