"""Regression tests for unified ANN answer orchestration."""

from unittest.mock import patch

from django.test import SimpleTestCase

from chatbot.ann.pipeline import answer_with_ann
from chatbot.rag import SAFE_FALLBACK


class ANNPipelineTests(SimpleTestCase):

    def setUp(self):
        self.record = {
            "protocol_id": 14,
            "protocol": "MRI",
            "step_id": 301,
            "step": "Remove jewellery",
            "instruction": "Remove jewellery before the scan.",
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

    def test_general_help_without_protocol(self):
        result = answer_with_ann("What can you help me with?")

        self.assertIn("PrepBuddy", result["answer"])
        self.assertFalse(result["needs_clinical_team"])
        self.assertEqual(result["sources"], [])
        self.retrieve.assert_not_called()

    def test_medication_question_escalates(self):
        result = answer_with_ann(
            "Can I take my medication?",
            protocol_id=14,
        )

        self.assertTrue(result["needs_clinical_team"])
        self.assertEqual(result["sources"], [])
        self.retrieve.assert_not_called()

    def test_requires_human_escalates(self):
        result = answer_with_ann(
            "When should I arrive?",
            protocol_id=14,
            requires_human=True,
        )

        self.assertTrue(result["needs_clinical_team"])
        self.retrieve.assert_not_called()

    def test_missing_protocol_prevents_retrieval(self):
        result = answer_with_ann(
            "Should I remove jewellery?",
        )

        self.assertTrue(result["needs_clinical_team"])
        self.assertEqual(result["sources"], [])
        self.retrieve.assert_not_called()

    def test_invalid_protocol_ids(self):
        for protocol_id in (0, -1, True, "14", 1.5):
            with self.subTest(protocol_id=protocol_id):
                result = answer_with_ann(
                    "Should I remove jewellery?",
                    protocol_id=protocol_id,
                )

                self.assertTrue(result["needs_clinical_team"])

        self.retrieve.assert_not_called()

    def test_procedure_mismatch_prevents_retrieval(self):
        result = answer_with_ann(
            "What should I do before my CT?",
            protocol_id=14,
        )

        self.assertTrue(result["needs_clinical_team"])
        self.assertIn("does not match", result["answer"])
        self.retrieve.assert_not_called()

    def test_multiple_procedures_require_clarification(self):
        result = answer_with_ann(
            "What should I do before my CT and MRI?",
            protocol_id=14,
        )

        self.assertIn("more than one test", result["answer"])
        self.assertEqual(result["sources"], [])
        self.retrieve.assert_not_called()

    def test_ambiguous_object_requires_clarification(self):
        result = answer_with_ann(
            "Should I remove it?",
            protocol_id=14,
        )

        self.assertIn("Which item", result["answer"])
        self.retrieve.assert_not_called()

    def test_preparation_overview_routing(self):
        overview = {
            "answer": "Synthetic stored protocol overview.",
            "sources": [self.record],
            "needs_clinical_team": False,
        }

        with patch(
            "chatbot.ann.pipeline.build_protocol_overview",
            return_value=overview,
        ) as builder:
            result = answer_with_ann(
                "What should I do to prepare for my procedure?",
                protocol_id=14,
            )

        self.assertEqual(result, overview)

        builder.assert_called_once_with(
            14,
            communication_style="neutral",
        )

        self.retrieve.assert_not_called()

    def test_unavailable_overview_returns_fallback(self):
        with patch(
            "chatbot.ann.pipeline.build_protocol_overview",
            return_value=None,
        ):
            result = answer_with_ann(
                "What should I do to prepare for my procedure?",
                protocol_id=14,
            )

        self.assertEqual(result["answer"], SAFE_FALLBACK)
        self.assertTrue(result["needs_clinical_team"])
        self.retrieve.assert_not_called()

    def test_overview_failure_returns_fallback(self):
        with patch(
            "chatbot.ann.pipeline.build_protocol_overview",
            side_effect=RuntimeError("Synthetic database failure"),
        ):
            result = answer_with_ann(
                "How should I prepare?",
                protocol_id=14,
            )

        self.assertEqual(result["answer"], SAFE_FALLBACK)
        self.assertEqual(result["sources"], [])
        self.assertTrue(result["needs_clinical_team"])
        self.retrieve.assert_not_called()

    def test_nonclinical_protocol_is_blocked(self):
        with patch(
            "chatbot.ann.pipeline.build_protocol_overview",
        ) as builder:

            for question in (
                "How should I prepare?",
                "Should I remove my earrings?",
            ):
                with self.subTest(question=question):
                    result = answer_with_ann(
                        question,
                        protocol_id=16,
                    )

                    self.assertEqual(
                        result["answer"],
                        SAFE_FALLBACK,
                    )
                    self.assertTrue(
                        result["needs_clinical_team"]
                    )

        builder.assert_not_called()
        self.retrieve.assert_not_called()

    def test_overview_preserves_communication_style(self):
        with patch(
            "chatbot.ann.pipeline.build_protocol_overview",
            return_value={
                "answer": "Synthetic overview.",
                "sources": [],
                "needs_clinical_team": False,
            },
        ) as builder:
            answer_with_ann(
                "How should I prepare?",
                protocol_id=14,
                communication_style="anxious",
            )

        builder.assert_called_once_with(
            14,
            communication_style="anxious",
        )

        self.retrieve.assert_not_called()

    def test_specific_question_uses_scoped_e5_retrieval(self):
        answer_with_ann(
            "Should I remove my earrings?",
            protocol_id=14,
        )

        self.retrieve.assert_called_once_with(
            "Should I remove my earrings?",
            protocol_id=14,
            limit=10,
        )

    def test_unvalidated_candidate_returns_safe_fallback(self):
        result = answer_with_ann(
            "Should I remove my earrings?",
            protocol_id=14,
        )

        self.assertEqual(result["answer"], SAFE_FALLBACK)
        self.assertEqual(result["sources"], [])
        self.assertTrue(result["needs_clinical_team"])

    def test_empty_retrieval_returns_safe_fallback(self):
        self.retrieve.return_value = []

        result = answer_with_ann(
            "Should I remove my earrings?",
            protocol_id=14,
        )

        self.assertEqual(result["answer"], SAFE_FALLBACK)

    def test_retrieval_failure_returns_safe_fallback(self):
        self.retrieve.side_effect = RuntimeError("Test failure")

        result = answer_with_ann(
            "Should I remove my earrings?",
            protocol_id=14,
        )

        self.assertEqual(result["answer"], SAFE_FALLBACK)
        self.assertTrue(result["needs_clinical_team"])

    def test_cross_protocol_candidate_is_not_returned(self):
        self.retrieve.return_value = [
            {**self.record, "protocol_id": 12}
        ]

        result = answer_with_ann(
            "Should I remove my earrings?",
            protocol_id=14,
        )

        self.assertEqual(result["answer"], SAFE_FALLBACK)
        self.assertEqual(result["sources"], [])

    def test_invalid_question_returns_safe_fallback(self):
        for question in (None, "", " ", 42):
            with self.subTest(question=question):
                result = answer_with_ann(
                    question,
                    protocol_id=14,
                )

                self.assertEqual(
                    result["answer"],
                    SAFE_FALLBACK,
                )

        self.retrieve.assert_not_called()
