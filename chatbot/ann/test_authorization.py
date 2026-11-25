"""Regression tests for conservative evidence authorization."""

from unittest import TestCase

from chatbot.ann.authorization import authorize_evidence


class AuthorizationTests(TestCase):

    def setUp(self):
        self.record = {
            "protocol_id": 14,
            "protocol": "MRI",
            "step_id": 301,
            "step": "Remove earrings",
            "instruction": "Remove earrings before the scan.",
            "similarity": 0.91,
        }

    def authorize(self, question, record=None):
        return authorize_evidence(
            question,
            self.record if record is None else record,
            protocol_id=14,
        )

    def test_directly_supported_removal_question(self):
        self.assertTrue(
            self.authorize("Should I remove my earrings?")
        )

    def test_unsupported_consequence_question(self):
        self.assertFalse(
            self.authorize(
                "What happens if I wear my earrings?"
            )
        )

    def test_unsupported_why_question(self):
        self.assertFalse(
            self.authorize("Why should I remove my earrings?")
        )

    def test_different_item_is_not_authorized(self):
        self.assertFalse(
            self.authorize("Should I remove my watch?")
        )

    def test_unrelated_question_is_not_authorized(self):
        self.assertFalse(
            self.authorize("Can I drink coffee?")
        )

    def test_cross_protocol_evidence_is_rejected(self):
        self.assertFalse(
            self.authorize(
                "Should I remove my earrings?",
                {**self.record, "protocol_id": 12},
            )
        )

    def test_mention_without_removal_instruction_is_rejected(self):
        self.assertFalse(
            self.authorize(
                "Should I remove my earrings?",
                {
                    **self.record,
                    "instruction": (
                        "Tell the department about your earrings."
                    ),
                },
            )
        )

    def test_high_similarity_does_not_override_relevance(self):
        self.assertFalse(
            self.authorize(
                "When should I arrive?",
                {**self.record, "similarity": 0.99},
            )
        )

    def test_explicit_instruction_lookup(self):
        self.assertTrue(
            self.authorize(
                "Repeat the remove earrings instruction."
            )
        )

    def test_invalid_question(self):
        for question in (None, "", " ", 42):
            with self.subTest(question=question):
                self.assertFalse(self.authorize(question))
