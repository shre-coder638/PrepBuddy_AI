
import json
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from patients.models import Patient
from protocols.models import PrepProtocol, PrepStep
from reminders.models import Reminder
from procedures.models import Procedure


class CreateProcedureAPITests(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(
            first_name="Test",
            last_name="Patient",
            phone_number="+919999000002",
        )
        self.protocol = PrepProtocol.objects.create(
            name="Test protocol",
            is_active=True,
        )
        PrepStep.objects.create(
            protocol=self.protocol,
            title="Step one",
            instruction="Test instruction",
            minutes_before_procedure=60,
        )
        PrepStep.objects.create(
            protocol=self.protocol,
            title="Step two",
            instruction="Test instruction",
            minutes_before_procedure=30,
        )

    def post_procedure(self, **overrides):
        payload = {
            "patient_id": self.patient.id,
            "protocol_id": self.protocol.id,
            "procedure_name": "Test procedure",
            "scheduled_at": (
                timezone.now() + timedelta(days=3)
            ).isoformat(),
        }
        payload.update(overrides)
        return self.client.post(
            "/api/procedures/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_creates_procedure_and_reminders(self):
        response = self.post_procedure()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["reminders_created"], 2)
        procedure = Procedure.objects.get()
        reminders = Reminder.objects.filter(procedure=procedure)

        self.assertEqual(reminders.count(), 2)
        self.assertTrue(all(r.confirmation_token for r in reminders))

    def test_procedures_url_supports_get_and_post(self):
        get_response = self.client.get("/api/procedures/")
        self.assertEqual(get_response.status_code, 200)
        self.assertIn("procedures", get_response.json())

        post_response = self.post_procedure()
        self.assertEqual(post_response.status_code, 201)
        self.assertEqual(Procedure.objects.count(), 1)

    def test_rejects_invalid_json(self):
        response = self.client.post(
            "/api/procedures/",
            data="{invalid",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_missing_fields(self):
        response = self.client.post(
            "/api/procedures/",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_naive_datetime(self):
        response = self.post_procedure(
            scheduled_at="2026-11-01T08:00:00"
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_inactive_protocol(self):
        self.protocol.is_active = False
        self.protocol.save()

        response = self.post_procedure()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Procedure.objects.count(), 0)
