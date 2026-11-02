from unittest.mock import Mock, patch

from django.test import SimpleTestCase
import requests

from chatbot.response_generator import (
    _has_unsupported_numbers,
    generate_patient_explanation,
    apply_communication_style,
    select_communication_style,
    COMMUNICATION_PREFIXES,
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
    def test_generation_rejects_new_numeric_details(self, post):
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

    def test_anxious_style_adds_reassuring_prefix_without_changing_instruction(self):
        instruction = "Stored instruction - Fasting: Do not eat after midnight."
        result = apply_communication_style(instruction, "anxious")
        self.assertTrue(result.startswith(
            "I understand this may feel worrying. I'll explain the instruction clearly."
        ))
        self.assertTrue(result.endswith(instruction))

    def test_confused_style_adds_simple_language_prefix(self):
        instruction = "Stored instruction - Arrival: Arrive at 08:30."
        result = apply_communication_style(instruction, "confused")
        self.assertTrue(result.startswith(
            "Let's go through the instruction in simpler language."
        ))
        self.assertTrue(result.endswith(instruction))

    def test_neutral_style_leaves_instruction_unchanged(self):
        instruction = "Stored instruction - Arrival: Arrive at 08:30."
        self.assertEqual(apply_communication_style(instruction, "neutral"), instruction)

    def test_unknown_style_falls_back_to_neutral(self):
        instruction = "Stored instruction - Arrival: Arrive at 08:30."
        self.assertEqual(apply_communication_style(instruction, "unknown"), instruction)



class CommunicationStyleSelectionTests(SimpleTestCase):
    def test_specific_emotions_take_priority_over_positive_sentiment(self):
        for emotion in ("anxious", "confused", "frustrated", "distressed"):
            with self.subTest(emotion=emotion):
                self.assertEqual(
                    select_communication_style("positive", emotion), emotion
                )

    def test_positive_sentiment_uses_positive_style_when_emotion_is_calm(self):
        self.assertEqual(select_communication_style("positive", "calm"), "positive")

    def test_negative_or_neutral_calm_message_uses_neutral_style(self):
        self.assertEqual(select_communication_style("negative", "calm"), "neutral")
        self.assertEqual(select_communication_style("neutral", "calm"), "neutral")

    def test_unknown_values_safely_use_neutral_style(self):
        self.assertEqual(select_communication_style("unknown", "unknown"), "neutral")

    def test_style_prefix_uses_real_line_breaks(self):
        answer = apply_communication_style("Stored instruction.", "anxious")
        self.assertIn("\n\n", answer)
        self.assertNotIn(r"\n", answer)
        self.assertTrue(answer.endswith("Stored instruction."))

    def test_all_supported_styles_add_their_prefix(self):
        instruction = "Stored instruction."
        for style in ("anxious", "confused", "frustrated", "distressed", "positive"):
            with self.subTest(style=style):
                result = apply_communication_style(instruction, style)
                self.assertTrue(result.startswith(COMMUNICATION_PREFIXES[style]))
                self.assertTrue(result.endswith(instruction))
