"""Regression tests for assigned-protocol mismatch safeguards."""

from unittest import TestCase

from chatbot.ann.clarification import assess_clarification


class ProcedureMismatchTests(TestCase):

    def test_matching_procedure(self):
        result = assess_clarification(
            "What should I do before my MRI?",
            active_protocol_id=14,
        )
        self.assertFalse(result["required"])

    def test_mismatched_procedure(self):
        result = assess_clarification(
            "What should I do before my CT?",
            active_protocol_id=14,
        )
        self.assertTrue(result["required"])
        self.assertEqual(result["kind"], "procedure_mismatch")

    def test_reverse_procedure_mismatch(self):
        result = assess_clarification(
            "What should I do before my MRI?",
            active_protocol_id=12,
        )
        self.assertTrue(result["required"])
        self.assertEqual(result["kind"], "procedure_mismatch")

    def test_hindi_procedure_mismatch(self):
        question = (
            "\u090f\u092e\u0906\u0930\u0906\u0908 "
            "\u0938\u0947 "
            "\u092a\u0939\u0932\u0947 "
            "\u0915\u094d\u092f\u093e "
            "\u0915\u0930\u0928\u093e "
            "\u091a\u093e\u0939\u093f\u090f?"
        )

        result = assess_clarification(
            question,
            active_protocol_id=12,
        )
        self.assertTrue(result["required"])
        self.assertEqual(result["kind"], "procedure_mismatch")

    def test_hinglish_procedure_mismatch(self):
        result = assess_clarification(
            "MRI se pehle kya karna chahiye?",
            active_protocol_id=12,
        )
        self.assertTrue(result["required"])
        self.assertEqual(result["kind"], "procedure_mismatch")

    def test_general_preparation_question(self):
        result = assess_clarification(
            "What should I do before my procedure?",
            active_protocol_id=14,
        )
        self.assertFalse(result["required"])

    def test_multiple_procedures_require_clarification(self):
        result = assess_clarification(
            "What should I do before my CT and MRI?",
            active_protocol_id=14,
        )
        self.assertTrue(result["required"])
        self.assertEqual(result["kind"], "procedure")

    def test_explicit_procedure_without_assigned_protocol(self):
        result = assess_clarification(
            "What should I do before my MRI?",
        )
        self.assertFalse(result["required"])
