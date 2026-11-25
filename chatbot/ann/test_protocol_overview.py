"""Regression tests for stored protocol overview generation."""

from unittest.mock import patch

from django.test import SimpleTestCase

from chatbot.ann.protocol_overview import build_protocol_overview


class ProtocolOverviewTests(SimpleTestCase):

    def setUp(self):
        self.records = [
            {
                "protocol_id": 14,
                "protocol": "Synthetic MRI Test Protocol",
                "step_id": 301,
                "step": "First stored step",
                "instruction": "First synthetic test instruction.",
                "minutes_before_procedure": 120,
                "order": 1,
                "is_critical": True,
                "requires_confirmation": True,
            },
            {
                "protocol_id": 14,
                "protocol": "Synthetic MRI Test Protocol",
                "step_id": 302,
                "step": "Second stored step",
                "instruction": "Second synthetic test instruction.",
                "minutes_before_procedure": 0,
                "order": 2,
                "is_critical": False,
                "requires_confirmation": False,
            },
        ]

        loader_patch = patch(
            "chatbot.ann.protocol_overview.load_protocol_records",
            return_value=self.records,
        )

        self.loader = loader_patch.start()
        self.addCleanup(loader_patch.stop)

    def test_complete_overview_contains_all_instructions(self):
        result = build_protocol_overview(14)

        for record in self.records:
            self.assertIn(
                record["instruction"],
                result["answer"],
            )

        self.assertEqual(len(result["sources"]), 2)
        self.assertFalse(result["needs_clinical_team"])

    def test_assigned_protocol_is_used(self):
        build_protocol_overview(14)

        self.loader.assert_called_once_with(14)

    def test_original_order_is_preserved(self):
        result = build_protocol_overview(14)

        self.assertLess(
            result["answer"].index("First stored step"),
            result["answer"].index("Second stored step"),
        )

    def test_critical_metadata_is_preserved(self):
        result = build_protocol_overview(14)

        self.assertTrue(
            result["sources"][0]["is_critical"]
        )
        self.assertTrue(
            result["sources"][0]["requires_confirmation"]
        )

    def test_timing_metadata_is_not_invented_as_deadline(self):
        result = build_protocol_overview(14)

        self.assertNotIn("120 minutes", result["answer"])

        self.assertEqual(
            result["sources"][0]["minutes_before_procedure"],
            120,
        )

    def test_no_records_returns_none(self):
        self.loader.return_value = []

        self.assertIsNone(build_protocol_overview(14))

    def test_cross_protocol_records_are_rejected(self):
        self.loader.return_value = [
            self.records[0],
            {**self.records[1], "protocol_id": 12},
        ]

        self.assertIsNone(build_protocol_overview(14))

    def test_duplicate_steps_are_rejected(self):
        self.loader.return_value = [
            self.records[0],
            self.records[0],
        ]

        self.assertIsNone(build_protocol_overview(14))

    def test_nonclinical_qa_protocol_is_rejected(self):
        self.loader.return_value = [
            {
                **self.records[0],
                "protocol_id": 16,
                "protocol": "PrepBuddy QA - Non-clinical test only",
            }
        ]

        self.assertIsNone(build_protocol_overview(16))

    def test_blank_instruction_is_rejected(self):
        self.loader.return_value = [
            {
                **self.records[0],
                "instruction": " ",
            }
        ]

        self.assertIsNone(build_protocol_overview(14))

    def test_communication_style_preserves_instructions(self):
        result = build_protocol_overview(
            14,
            communication_style="anxious",
        )

        for record in self.records:
            self.assertIn(
                record["instruction"],
                result["answer"],
            )
