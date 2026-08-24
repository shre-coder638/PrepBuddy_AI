from django.db import models


class PrepProtocol(models.Model):
    """A reusable preparation protocol for a medical procedure."""

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class PrepStep(models.Model):
    """A single preparation instruction within a protocol."""

    protocol = models.ForeignKey(
        PrepProtocol,
        on_delete=models.CASCADE,
        related_name="steps"
    )

    title = models.CharField(max_length=200)
    instruction = models.TextField()

    # Number of minutes before the procedure when this step occurs
    minutes_before_procedure = models.PositiveIntegerField()

    # Determines whether patient confirmation is required
    requires_confirmation = models.BooleanField(default=True)

    # Critical steps trigger alerts if not confirmed
    is_critical = models.BooleanField(default=False)

    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-minutes_before_procedure", "order"]

    def __str__(self):
        return f"{self.protocol.name} - {self.title}"