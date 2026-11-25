"""Tests for conservative preparation overview detection."""

from unittest import TestCase

from chatbot.ann.preparation_intent import is_preparation_overview


class PreparationIntentTests(TestCase):

    def test_general_preparation_questions(self):
        questions = (
            "What should I do to prepare for my procedure?",
            "What should I do before my procedure?",
            "How should I prepare for my procedure?",
            "How do I prepare?",
            "Show me my preparation instructions",
            "What are my preparation steps?",
        )

        for question in questions:
            with self.subTest(question=question):
                self.assertTrue(
                    is_preparation_overview(question)
                )

    def test_hinglish_overview(self):
        for question in (
            "Procedure se pehle kya karna chahiye?",
            "Taiyari kaise karun?",
            "Scan se pehle kya karna chahiye?",
        ):
            with self.subTest(question=question):
                self.assertTrue(
                    is_preparation_overview(question)
                )

    def test_hindi_overview(self):
        question = (
            "\u092e\u0941\u091d\u0947 "
            "\u0915\u094d\u092f\u093e "
            "\u0924\u0948\u092f\u093e\u0930\u0940 "
            "\u0915\u0930\u0928\u0940 "
            "\u091a\u093e\u0939\u093f\u090f?"
        )

        self.assertTrue(
            is_preparation_overview(question)
        )

    def test_specific_questions_are_not_overviews(self):
        questions = (
            "Can I eat before my procedure?",
            "Can I drink black coffee?",
            "When should I arrive?",
            "Should I remove my earrings?",
            "When will I receive my results?",
            "Can I take my medication?",
            "What is the weather tomorrow?",
        )

        for question in questions:
            with self.subTest(question=question):
                self.assertFalse(
                    is_preparation_overview(question)
                )

    def test_mixed_clinical_question_is_not_overview(self):
        question = (
            "How should I prepare for my procedure "
            "if I missed my medication?"
        )

        self.assertFalse(
            is_preparation_overview(question)
        )

    def test_normalization(self):
        self.assertTrue(
            is_preparation_overview(
                "  HOW   SHOULD I PREPARE???  "
            )
        )

    def test_empty_question(self):
        for question in ("", " ", "???"):
            with self.subTest(question=question):
                self.assertFalse(
                    is_preparation_overview(question)
                )

    def test_invalid_input(self):
        for question in (None, 42, True):
            with self.subTest(question=question):
                with self.assertRaises(TypeError):
                    is_preparation_overview(question)
