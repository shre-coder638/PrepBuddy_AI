
from django.db import models
from uuid import uuid4

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
    confirmed_reminder = models.ForeignKey(
        "reminders.Reminder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmation_messages",
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
    email_claimed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    last_error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Staff alert for reminder {self.reminder_id}"


class WhatsAppMessageAnalysis(models.Model):
    """Communication analysis for one patient-authored WhatsApp message."""

    SENTIMENT_CHOICES = [
        ("positive", "Positive"),
        ("neutral", "Neutral"),
        ("negative", "Negative"),
    ]
    EMOTION_CHOICES = [
        ("calm", "Calm"),
        ("anxious", "Anxious"),
        ("confused", "Confused"),
        ("frustrated", "Frustrated"),
        ("distressed", "Distressed"),
    ]
    INTENT_CHOICES = [
        ("instruction_question", "Instruction question"),
        ("clarification", "Clarification"),
        ("acknowledgement", "Acknowledgement"),
        ("help_request", "Help request"),
        ("clinical_concern", "Clinical concern"),
        ("other", "Other"),
    ]

    message = models.OneToOneField(
        WhatsAppConversationMessage,
        on_delete=models.CASCADE,
        related_name="analysis",
    )
    sentiment = models.CharField(max_length=12, choices=SENTIMENT_CHOICES)
    emotion = models.CharField(max_length=12, choices=EMOTION_CHOICES)
    intent = models.CharField(max_length=32, choices=INTENT_CHOICES)
    confidence = models.FloatField(default=0.0)
    requires_human = models.BooleanField(default=False)
    model_version = models.CharField(max_length=40, default="rules-v1")
    analyzed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-analyzed_at"]

    def __str__(self):
        return f"Analysis for message {self.message_id}: {self.sentiment}/{self.intent}"

class WhatsAppOutboundMessage(models.Model):
    """Durable record of one logical outbound WhatsApp message."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sending", "Sending"),
        ("accepted", "Accepted by OpenWA"),
        ("unknown", "Outcome unknown"),
        ("failed", "Failed"),
        ("expired", "Idempotency window expired"),
    ]

    DELIVERY_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("read", "Read"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False,
    )
    purpose = models.CharField(max_length=40)
    dedupe_key = models.CharField(max_length=255, unique=True)

    openwa_session_id = models.CharField(max_length=100)
    chat_id = models.CharField(max_length=255)
    message_text = models.TextField()
    payload_sha256 = models.CharField(max_length=64)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    delivery_status = models.CharField(
        max_length=20,
        choices=DELIVERY_STATUS_CHOICES,
        default="pending",
    )
    attempts = models.PositiveSmallIntegerField(default=0)

    lease_until = models.DateTimeField(null=True, blank=True)
    first_attempt_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    openwa_message_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    last_error = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["status", "lease_until"],
                name="wa_out_status_lease_idx",
            ),
        ]

    def __str__(self):
        return f"{self.purpose} - {self.id} - {self.status}"
