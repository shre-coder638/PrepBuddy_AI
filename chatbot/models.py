"""Persistent experience and reviewed learning data for PrepBuddy ANN."""

import uuid

from django.conf import settings
from django.db import models


class ANNExperience(models.Model):

    class Outcome(models.TextChoices):
        GROUNDED = "grounded", "Grounded response"
        OVERVIEW = "overview", "Protocol overview"
        ABSTENTION = "abstention", "Abstention"
        ESCALATION = "escalation", "Clinical escalation"
        CLARIFICATION = "clarification", "Clarification"
        GENERAL_HELP = "general_help", "General help"
        ERROR = "error", "Processing error"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    protocol_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
    )

    model_version = models.CharField(
        max_length=100,
    )

    feature_version = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    outcome = models.CharField(
        max_length=30,
        choices=Outcome.choices,
        db_index=True,
    )

    retrieved_step_ids = models.JSONField(
        default=list,
        blank=True,
    )

    returned_step_ids = models.JSONField(
        default=list,
        blank=True,
    )

    needs_clinical_team = models.BooleanField(
        default=False,
    )

    latency_ms = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["protocol_id", "outcome"],
                name="ann_exp_protocol_outcome",
            ),
        ]

    def __str__(self):
        return f"{self.id} - {self.outcome}"


class ANNReviewedExample(models.Model):

    class Relevance(models.TextChoices):
        DIRECT = "direct_support", "Direct support"
        PARTIAL = "partial_support", "Partial support"
        IRRELEVANT = "irrelevant", "Irrelevant"
        CONFLICTING = "conflicting", "Conflicting"

    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        HINDI = "hi", "Hindi"
        HINGLISH = "hinglish", "Hinglish"
        OTHER = "other", "Other"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    experience = models.ForeignKey(
        ANNExperience,
        on_delete=models.PROTECT,
        related_name="reviewed_examples",
    )

    question = models.TextField(
        help_text="De-identified question only.",
    )

    language = models.CharField(
        max_length=20,
        choices=Language.choices,
    )

    protocol_id = models.PositiveIntegerField()

    step_id = models.PositiveIntegerField()

    instruction_snapshot = models.TextField()

    instruction_sha256 = models.CharField(
        max_length=64,
    )

    relevance_label = models.CharField(
        max_length=30,
        choices=Relevance.choices,
        null=True,
        blank=True,
    )

    requires_escalation = models.BooleanField(
        null=True,
        blank=True,
    )

    review_status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
        db_index=True,
    )

    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="ann_reviewed_examples",
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    review_notes = models.TextField(
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "experience",
                    "step_id",
                ],
                name="ann_unique_experience_step",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(review_status="approved")
                    |
                    (
                        models.Q(reviewer__isnull=False)
                        & models.Q(reviewed_at__isnull=False)
                        & models.Q(
                            relevance_label__in=[
                                "direct_support",
                                "partial_support",
                                "irrelevant",
                                "conflicting",
                            ]
                        )
                        & models.Q(relevance_label__isnull=False)
                        & models.Q(requires_escalation__isnull=False)
                    )
                ),
                name="ann_approved_requires_review",
            ),
        ]

        indexes = [
            models.Index(
                fields=["review_status", "language"],
                name="ann_review_status_lang",
            ),
        ]

    def __str__(self):
        return f"{self.id} - {self.review_status}"
