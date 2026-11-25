"""Regression tests for ANN evidence candidate selection."""

from unittest import TestCase

from chatbot.ann.evidence import (
    is_valid_evidence,
    select_candidate_evidence,
)


class EvidenceTests(TestCase):

    def setUp(self):
        self.record = {
            "protocol_id": 14,
            "protocol": "MRI",
            "step_id": 301,
            "step": "Remove jewellery",
            "instruction": "Remove jewellery before the scan.",
            "similarity": 0.91,
        }

    def select(self, question, records):
        return select_candidate_evidence(
            question,
            records,
            protocol_id=14,
        )

    def test_valid_evidence(self):
        self.assertTrue(is_valid_evidence(self.record, 14))

    def test_explicit_concept_match(self):
        results = self.select(
            "Should I remove my earrings?",
            [self.record],
        )
        self.assertEqual(len(results), 1)

    def test_unrelated_question_rejected(self):
        results = self.select(
            "What is the weather tomorrow?",
            [self.record],
        )
        self.assertEqual(results, [])

    def test_high_similarity_alone_is_insufficient(self):
        record = {**self.record, "similarity": 0.99}
        results = self.select(
            "Can I drink black coffee?",
            [record],
        )
        self.assertEqual(results, [])

    def test_cross_protocol_evidence_rejected(self):
        record = {**self.record, "protocol_id": 12}
        results = self.select(
            "Should I remove my earrings?",
            [record],
        )
        self.assertEqual(results, [])

    def test_duplicate_evidence_removed(self):
        results = self.select(
            "Should I remove my earrings?",
            [self.record, self.record],
        )
        self.assertEqual(len(results), 1)

    def test_invalid_similarity_rejected(self):
        for score in (None, True, float("nan"), float("inf"), 2.0):
            with self.subTest(score=score):
                record = {**self.record, "similarity": score}
                self.assertFalse(is_valid_evidence(record, 14))

    def test_empty_instruction_rejected(self):
        for instruction in ("", " ", "-", ".", "n/a"):
            with self.subTest(instruction=instruction):
                record = {
                    **self.record,
                    "instruction": instruction,
                }
                self.assertFalse(is_valid_evidence(record, 14))

    def test_missing_metadata_rejected(self):
        for field in (
            "protocol_id",
            "protocol",
            "step_id",
            "step",
            "instruction",
            "similarity",
        ):
            with self.subTest(field=field):
                record = dict(self.record)
                record.pop(field)
                self.assertFalse(is_valid_evidence(record, 14))

    def test_empty_retrieval_results(self):
        self.assertEqual(
            self.select("Should I remove jewellery?", []),
            [],
        )

    def test_invalid_protocol_id(self):
        for protocol_id in (None, True, 0, -1, "14"):
            with self.subTest(protocol_id=protocol_id):
                with self.assertRaises(ValueError):
                    select_candidate_evidence(
                        "Should I remove jewellery?",
                        [self.record],
                        protocol_id=protocol_id,
                    )
