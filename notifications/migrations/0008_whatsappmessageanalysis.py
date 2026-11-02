from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0007_whatsappconversationmessage"),
    ]

    operations = [
        migrations.CreateModel(
            name="WhatsAppMessageAnalysis",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sentiment", models.CharField(choices=[("positive", "Positive"), ("neutral", "Neutral"), ("negative", "Negative")], max_length=12)),
                ("emotion", models.CharField(choices=[("calm", "Calm"), ("anxious", "Anxious"), ("confused", "Confused"), ("frustrated", "Frustrated"), ("distressed", "Distressed")], max_length=12)),
                ("intent", models.CharField(choices=[("instruction_question", "Instruction question"), ("clarification", "Clarification"), ("acknowledgement", "Acknowledgement"), ("help_request", "Help request"), ("clinical_concern", "Clinical concern"), ("other", "Other")], max_length=32)),
                ("confidence", models.FloatField(default=0.0)),
                ("requires_human", models.BooleanField(default=False)),
                ("model_version", models.CharField(default="rules-v1", max_length=40)),
                ("analyzed_at", models.DateTimeField(auto_now_add=True)),
                ("message", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="analysis", to="notifications.whatsappconversationmessage")),
            ],
            options={"ordering": ["-analyzed_at"]},
        ),
    ]
