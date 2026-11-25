from unittest.mock import patch

import numpy as np
from django.test import SimpleTestCase

from chatbot.ann import e5_retrieval as e5


class MockE5Model:
    """Deterministic model substitute; no model download or inference."""

    def __init__(self, vectors):
        self.vectors = vectors
        self.calls = []

    def encode(self, texts, **kwargs):
        self.calls.append((list(texts), kwargs))
        vectors = np.array(
            [self.vectors[text] for text in texts],
            dtype=np.float32,
        )
        return vectors


class E5RetrievalTests(SimpleTestCase):

    def setUp(self):
        e5.clear_e5_cache()

        self.records = [
            {
                "protocol_id": 11,
                "protocol": "Colonoscopy",
                "step_id": 101,
                "step": "Food instructions",
                "instruction": "Follow the approved food instructions.",
                "text": "record one",
                "is_critical": True,
                "requires_confirmation": False,
            },
            {
                "protocol_id": 12,
                "protocol": "CT",
                "step_id": 201,
                "step": "Preparation",
                "instruction": "Follow the approved CT instructions.",
                "text": "record two",
                "is_critical": False,
                "requires_confirmation": True,
            },
            {
                "protocol_id": 14,
                "protocol": "MRI",
                "step_id": 301,
                "step": "Metal objects",
                "instruction": "Follow the MRI department's instructions.",
                "text": "record three",
                "is_critical": True,
                "requires_confirmation": True,
            },
        ]

        self.vectors = {
            "passage: record one": [1.0, 0.0, 0.0],
            "passage: updated record one": [1.0, 0.0, 0.0],
            "passage: record two": [0.0, 1.0, 0.0],
            "passage: record three": [0.0, 0.0, 1.0],
            "query: MRI preparation": [0.0, 0.0, 1.0],
            "query: tie": [1.0, 1.0, 0.0],
        }

        self.model = MockE5Model(self.vectors)

        self.model_patch = patch.object(
            e5,
            "_get_model",
            return_value=self.model,
        )
        self.model_patch.start()
        self.addCleanup(self.model_patch.stop)
        self.addCleanup(e5.clear_e5_cache)

        self.records_patch = patch(
            "chatbot.evaluation.load_protocols.load_active_protocols",
            return_value=self.records,
        )
        self.records_patch.start()
        self.addCleanup(self.records_patch.stop)

    def test_retrieves_best_matching_step_globally(self):
        results = e5.retrieve_e5_steps("MRI preparation")

        self.assertEqual(
            [item["step_id"] for item in results],
            [301, 101, 201],
        )
        self.assertEqual(results[0]["protocol_id"], 14)
        self.assertEqual(results[0]["instruction"], self.records[2]["instruction"])
        self.assertTrue(results[0]["is_critical"])
        self.assertTrue(results[0]["requires_confirmation"])

    def test_uses_exact_e5_prefixes_and_normalization(self):
        e5.retrieve_e5_steps("MRI preparation")

        self.assertEqual(
            self.model.calls[0][0],
            [
                "passage: record one",
                "passage: record two",
                "passage: record three",
            ],
        )
        self.assertEqual(
            self.model.calls[1][0],
            ["query: MRI preparation"],
        )

        for _, kwargs in self.model.calls:
            self.assertTrue(kwargs["convert_to_numpy"])
            self.assertTrue(kwargs["normalize_embeddings"])
            self.assertFalse(kwargs["show_progress_bar"])

    def test_passage_embeddings_are_cached(self):
        e5.retrieve_e5_steps("MRI preparation")
        e5.retrieve_e5_steps("MRI preparation")

        passage_calls = [
            call for call in self.model.calls
            if call[0] and call[0][0].startswith("passage: ")
        ]

        self.assertEqual(len(passage_calls), 1)

    def test_passage_cache_invalidates_when_source_changes(self):
        e5.retrieve_e5_steps("MRI preparation")

        changed_records = [
            dict(record)
            for record in self.records
        ]
        changed_records[0]["text"] = "updated record one"

        with patch(
            "chatbot.evaluation.load_protocols.load_active_protocols",
            return_value=changed_records,
        ):
            e5.retrieve_e5_steps("MRI preparation")

        passage_calls = [
            call for call in self.model.calls
            if call[0] and call[0][0].startswith("passage: ")
        ]

        self.assertEqual(len(passage_calls), 2)
        self.assertEqual(
            passage_calls[1][0][0],
            "passage: updated record one",
        )

    def test_equal_scores_use_original_record_order(self):
        results = e5.retrieve_e5_steps("tie", limit=2)

        self.assertEqual(
            [item["step_id"] for item in results],
            [101, 201],
        )

    def test_limit_is_respected(self):
        results = e5.retrieve_e5_steps("MRI preparation", limit=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["step_id"], 301)

    def test_empty_protocol_database_returns_empty_list(self):
        with patch(
            "chatbot.evaluation.load_protocols.load_active_protocols",
            return_value=[],
        ):
            self.assertEqual(
                e5.retrieve_e5_steps("MRI preparation"),
                [],
            )

    def test_empty_question_is_rejected(self):
        with self.assertRaises(ValueError):
            e5.retrieve_e5_steps("   ")

    def test_non_string_question_is_rejected(self):
        with self.assertRaises(ValueError):
            e5.retrieve_e5_steps(None)

    def test_invalid_limit_is_rejected(self):
        for limit in (0, -1, 1.5, True):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    e5.retrieve_e5_steps("MRI preparation", limit=limit)
    def test_retrieval_is_restricted_to_assigned_protocol(self):
        results = e5.retrieve_e5_steps(
            "MRI preparation",
            protocol_id=11,
            limit=3,
        )

        self.assertEqual(
            [item["step_id"] for item in results],
            [101],
        )

        self.assertTrue(
            all(item["protocol_id"] == 11 for item in results)
        )

    def test_unknown_protocol_returns_no_results(self):
        results = e5.retrieve_e5_steps(
            "MRI preparation",
            protocol_id=99999,
        )

        self.assertEqual(results, [])
        self.assertEqual(self.model.calls, [])

    def test_invalid_protocol_ids_are_rejected(self):
        for protocol_id in (0, -1, True, "11", 1.5):
            with self.subTest(protocol_id=protocol_id):
                with self.assertRaises(ValueError):
                    e5.retrieve_e5_steps(
                        "MRI preparation",
                        protocol_id=protocol_id,
                    )

    def test_passage_cache_is_shared_across_protocols(self):
        for protocol_id in (11, 12, 14, 11):
            results = e5.retrieve_e5_steps(
                "MRI preparation",
                protocol_id=protocol_id,
            )

            self.assertTrue(results)
            self.assertTrue(
                all(
                    item["protocol_id"] == protocol_id
                    for item in results
                )
            )

        passage_calls = [
            call for call in self.model.calls
            if call[0] and call[0][0].startswith("passage: ")
        ]

        self.assertEqual(len(passage_calls), 1)

    def test_global_and_scoped_retrieval_share_cache(self):
        global_results = e5.retrieve_e5_steps(
            "MRI preparation",
        )

        scoped_results = e5.retrieve_e5_steps(
            "MRI preparation",
            protocol_id=14,
        )

        self.assertEqual(global_results[0]["step_id"], 301)
        self.assertEqual(len(scoped_results), 1)
        self.assertEqual(scoped_results[0]["step_id"], 301)

        passage_calls = [
            call for call in self.model.calls
            if call[0] and call[0][0].startswith("passage: ")
        ]

        self.assertEqual(len(passage_calls), 1)

