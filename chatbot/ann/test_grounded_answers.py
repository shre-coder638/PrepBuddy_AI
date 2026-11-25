"""Tests for authorized, source-grounded ANN answers."""

from unittest.mock import patch

from django.test import SimpleTestCase

from chatbot.ann.pipeline import answer_with_ann
from chatbot.rag import SAFE_FALLBACK


class GroundedAnswerTests(SimpleTestCase):

    def setUp(self):
        self.record = {
            "protocol_id": 14,
            "protocol": "MRI",
            "step_id": 301,
            "step": "Remove earrings",
            "instruction": "Remove earrings before the scan.",
            "similarity": 0.91,
            "minutes_before_procedure": 30,
            "is_critical": True,
            "requires_confirmation": False,
        }

        self.retrieval_patch = patch(
            "chatbot.ann.pipeline.retrieve_e5_steps",
            return_value=[self.record],
        )

        self.retrieve = self.retrieval_patch.start()
        self.addCleanup(self.retrieval_patch.stop)

    def test_authorized_question_returns_stored_instruction(self):
        result = answer_with_ann(
            "Should I remove my earrings?",
            protocol_id=14,
        )

        self.assertEqual(
            result["answer"],
            "Stored instruction - Remove earrings: "
            "Remove earrings before the scan.",
        )
        self.assertFalse(result["needs_clinical_team"])

    def test_source_metadata_is_preserved(self):
        result = answer_with_ann(
            "Should I remove my earrings?",
            protocol_id=14,
        )

        self.assertEqual(len(result["sources"]), 1)

        source = result["sources"][0]

        self.assertEqual(source["protocol_id"], 14)
        self.assertEqual(source["step_id"], 301)
        self.assertEqual(source["protocol"], "MRI")
        self.assertTrue(source["is_critical"])
        self.assertEqual(
            source["minutes_before_procedure"],
            30,
        )

    def test_unsupported_question_returns_fallback(self):
        result = answer_with_ann(
            "Why should I remove my earrings?",
            protocol_id=14,
        )

        self.assertEqual(result["answer"], SAFE_FALLBACK)
        self.assertEqual(result["sources"], [])
        self.assertTrue(result["needs_clinical_team"])

    def test_unrelated_item_returns_fallback(self):
        result = answer_with_ann(
            "Should I remove my watch?",
            protocol_id=14,
        )

        self.assertEqual(result["answer"], SAFE_FALLBACK)

    def test_cross_protocol_record_returns_fallback(self):
        self.retrieve.return_value = [
            {**self.record, "protocol_id": 12}
        ]

        result = answer_with_ann(
            "Should I remove my earrings?",
            protocol_id=14,
        )

        self.assertEqual(result["answer"], SAFE_FALLBACK)
        self.assertEqual(result["sources"], [])

    def test_communication_style_preserves_instruction(self):
        result = answer_with_ann(
            "Should I remove my earrings?",
            protocol_id=14,
            communication_style="anxious",
        )

        self.assertIn(
            self.record["instruction"],
            result["answer"],
        )

        self.assertFalse(result["needs_clinical_team"])

    def test_multiple_authorized_records_trigger_fallback(self):
        self.retrieve.return_value = [
            self.record,
            {
                **self.record,
                "step_id": 302,
                "instruction": (
                    "Remove earrings when instructed by staff."
                ),
            },
        ]

        result = answer_with_ann(
            "Should I remove my earrings?",
            protocol_id=14,
        )

        self.assertEqual(result["answer"], SAFE_FALLBACK)
        self.assertEqual(result["sources"], [])

    def test_medication_question_still_escalates(self):
        result = answer_with_ann(
            "Can I take my medication?",
            protocol_id=14,
        )

        self.assertTrue(result["needs_clinical_team"])
        self.retrieve.assert_not_called()
