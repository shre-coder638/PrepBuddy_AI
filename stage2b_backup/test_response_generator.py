from unittest.mock import Mock, patch

from django.test import SimpleTestCase
import requests

from chatbot.response_generator import (
    _has_unsupported_numbers,
    generate_patient_explanation,
)


class GeneratedExplanationTests(SimpleTestCase):
    def test_rejects_new_numeric_details(self):
        self.assertTrue(_has_unsupported_numbers(
            "Stop eating 8 hours before.", "Do not eat before the procedure."
        ))

    def test_accepts_numbers_already_in_source(self):
        self.assertFalse(_has_unsupported_numbers(
            "Arrive at 08:30.", "Please arrive at 08:30."
        ))

    @patch("chatbot.response_generator.requests.post")
    def test_returns_generated_explanation(self, post):
        post.return_value = Mock(
            status_code=200,
            json=lambda: {"message": {"content": "Please arrive at 08:30."}},
        )
        post.return_value.raise_for_status.return_value = None

        result = generate_patient_explanation(
            "When should I arrive?",
            "Please arrive at 08:30.",
            "confused",
        )

        self.assertEqual(result, "Please arrive at 08:30.")

    @patch("chatbot.response_generator.requests.post")
    def test_rejects_new_numeric_details(self, post):
        post.return_value = Mock(
            status_code=200,
            json=lambda: {"message": {"content": "Please arrive 2 hours early."}},
        )
        post.return_value.raise_for_status.return_value = None

        result = generate_patient_explanation(
            "When should I arrive?",
            "Please arrive at 08:30.",
        )

        self.assertIsNone(result)

    @patch("chatbot.response_generator.requests.post", side_effect=requests.ConnectionError("offline"))
    def test_generation_failure_falls_back(self, _post):
        # Unexpected errors should not escape to the webhook.
        self.assertIsNone(generate_patient_explanation(
            "What should I do?", "Follow the stored instruction."
        ))
