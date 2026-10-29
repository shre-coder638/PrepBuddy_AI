import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from frontend.models import StaffProfile
from patients.models import Patient
from procedures.models import Procedure
from protocols.models import PrepProtocol, PrepStep


class ChatbotAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="clinic_test",
            password="test-password-123",
        )
        StaffProfile.objects.create(
            user=self.user,
            role="clinic_staff",
        )

        self.patient = Patient.objects.create(
            first_name="Test",
            last_name="Patient",
            phone_number="+919999000011",
        )
        self.protocol = PrepProtocol.objects.create(
            name="Test preparation protocol",
            is_active=True,
        )
        PrepStep.objects.create(
            protocol=self.protocol,
            title="Preparation step",
            instruction="Follow the stored preparation instruction.",
            minutes_before_procedure=60,
        )
        self.procedure = Procedure.objects.create(
            patient=self.patient,
            protocol=self.protocol,
            procedure_name="Test procedure",
            scheduled_at=timezone.now() + timedelta(days=2),
        )

    def post_question(self, payload=None):
        return self.client.post(
            "/api/chatbot/",
            data=json.dumps(
                payload if payload is not None
                else {
                    "question": "What does my preparation instruction say?",
                    "procedure_id": self.procedure.id,
                }
            ),
            content_type="application/json",
        )

    def test_unauthenticated_request_is_rejected(self):
        response = self.post_question()
        self.assertEqual(response.status_code, 401)

    def test_user_without_staff_profile_is_rejected(self):
        user = User.objects.create_user(
            username="unlinked_user",
            password="test-password-123",
        )
        self.client.force_login(user)

        response = self.post_question()

        self.assertEqual(response.status_code, 403)

    def test_unsupported_staff_role_is_rejected(self):
        user = User.objects.create_user(
            username="unsupported_user",
            password="test-password-123",
        )
        StaffProfile.objects.create(user=user, role="clinic_staff")
        profile = user.staff_profile
        profile.role = "unsupported"
        profile.save()
        self.client.force_login(user)

        response = self.post_question()

        self.assertEqual(response.status_code, 403)

    @patch("chatbot.views.answer_with_rag")
    def test_question_uses_selected_procedure_protocol(self, mock_answer):
        self.client.force_login(self.user)
        mock_answer.return_value = {
            "answer": "Follow the stored instruction.",
            "sources": [],
            "needs_clinical_team": False,
        }

        response = self.post_question()

        self.assertEqual(response.status_code, 200)
        mock_answer.assert_called_once_with(
            "What does my preparation instruction say?",
            protocol_id=self.procedure.protocol_id,
        )

    def test_missing_procedure_id_is_rejected(self):
        self.client.force_login(self.user)

        response = self.post_question({
            "question": "What should I do?",
        })

        self.assertEqual(response.status_code, 400)

    def test_invalid_procedure_id_is_rejected(self):
        self.client.force_login(self.user)

        response = self.post_question({
            "question": "What should I do?",
            "procedure_id": "not-a-number",
        })

        self.assertEqual(response.status_code, 400)

    def test_nonexistent_procedure_returns_404(self):
        self.client.force_login(self.user)

        response = self.post_question({
            "question": "What should I do?",
            "procedure_id": 999999,
        })

        self.assertEqual(response.status_code, 404)

    @patch("chatbot.views.answer_with_rag")
    def test_safety_escalation_happens_before_rag(self, mock_answer):
        self.client.force_login(self.user)

        response = self.post_question({
            "question": "Should I change my medication before surgery?",
            "procedure_id": self.procedure.id,
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["needs_clinical_team"])
        mock_answer.assert_not_called()
