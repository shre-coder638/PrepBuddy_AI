
from unittest.mock import patch

from django.test import SimpleTestCase

from .rag import _cosine_similarity, retrieve_steps, answer_with_rag

class RagUtilityTests(SimpleTestCase):
    def test_cosine_similarity_identical_vectors(self):
        self.assertAlmostEqual(
            _cosine_similarity([1.0, 0.0], [1.0, 0.0]),
            1.0,
        )

    def test_cosine_similarity_orthogonal_vectors(self):
        self.assertAlmostEqual(
            _cosine_similarity([1.0, 0.0], [0.0, 1.0]),
            0.0,
        )

    def test_cosine_similarity_zero_vector(self):
        self.assertEqual(
            _cosine_similarity([0.0, 0.0], [1.0, 0.0]),
            0.0,
        )

    def test_cosine_similarity_different_dimensions(self):
        self.assertEqual(
            _cosine_similarity([1.0, 0.0], [1.0]),
            0.0,
        )

class RagBehaviorTests(SimpleTestCase):
    @patch("chatbot.rag.retrieve_steps")
    def test_no_matching_sources_returns_safe_fallback(self, mock_retrieve):
        mock_retrieve.return_value = []

        result = answer_with_rag("Unrelated question")

        self.assertEqual(result["sources"], [])
        self.assertTrue(result["needs_clinical_team"])
        self.assertIn("clinical team", result["answer"])

    @patch("chatbot.rag.retrieve_steps")
    @patch("chatbot.rag.requests.post")
    def test_ollama_failure_returns_safe_fallback(
        self,
        mock_post,
        mock_retrieve,
    ):
        # Semantic retrieval is the only required model operation
        # in the source-grounded answer implementation.
        mock_retrieve.side_effect = ConnectionError(
            "Ollama unavailable"
        )

        result = answer_with_rag("What should I do?")

        self.assertEqual(result["sources"], [])
        self.assertTrue(result["needs_clinical_team"])
        self.assertIn("clinical team", result["answer"])
        mock_post.assert_not_called()

    @patch("chatbot.rag.retrieve_steps")
    def test_medication_question_escalates_before_retrieval(
        self,
        mock_retrieve,
    ):
        result = answer_with_rag(
            "Should I change my medication before the procedure?"
        )

        self.assertTrue(result["needs_clinical_team"])
        self.assertEqual(result["sources"], [])
        mock_retrieve.assert_not_called()

    @patch("chatbot.rag._load_knowledge")
    @patch("chatbot.rag._embed_texts")
    def test_retrieval_ranks_relevant_steps(
        self,
        mock_embed,
        mock_load,
    ):
        mock_load.return_value = [
            {
                "protocol_id": 1,
                "content": "clear liquid diet",
                "protocol": "Colonoscopy Preparation",
                "step": "Avoid solid foods",
                "instruction": "Use the approved clear-liquid diet.",
                "minutes_before_procedure": 180,
                "is_critical": True,
                "embedding": [1.0, 0.0],
            },
            {
                "protocol_id": 1,
                "content": "confirmation",
                "protocol": "Colonoscopy Preparation",
                "step": "Final preparation confirmation",
                "instruction": "Confirm preparation status.",
                "minutes_before_procedure": 60,
                "is_critical": False,
                "embedding": [0.0, 1.0],
            },
        ]
        mock_embed.return_value = [[1.0, 0.0]]

        results = retrieve_steps("How do I follow the liquid diet?")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["step"], "Avoid solid foods")

    @patch("chatbot.rag.retrieve_steps")
    @patch("chatbot.rag.requests.post")
    def test_answer_uses_retrieved_evidence(
        self,
        mock_post,
        mock_retrieve,
    ):
        mock_retrieve.return_value = [
            {
                "protocol_id": 1,
                "protocol": "Colonoscopy Preparation",
                "step": "Avoid solid foods",
                "instruction": (
                    "Patient should transition to the approved "
                    "clear-liquid diet before the procedure."
                ),
                "minutes_before_procedure": 180,
                "is_critical": True,
                "similarity": 0.82,
            }
        ]

        result = answer_with_rag(
            "What does my stored instruction say?"
        )

        self.assertIn("clear-liquid diet", result["answer"])
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(
            result["sources"][0]["step"],
            "Avoid solid foods",
        )
        self.assertFalse(result["needs_clinical_team"])
        mock_post.assert_not_called()

    @patch("chatbot.rag.retrieve_steps")
    def test_unsupported_black_coffee_question_abstains(
        self, mock_retrieve,):
      mock_retrieve.return_value = []

      result = answer_with_rag("Can I drink black coffee?")

      self.assertEqual(result["sources"], [])
      self.assertTrue(result["needs_clinical_team"])
      self.assertIn("couldn't confidently find", result["answer"])

    @patch("chatbot.rag._load_knowledge")
    @patch("chatbot.rag._embed_texts")
    def test_retrieval_filters_by_protocol_id(
        self, mock_embed, mock_load
    ):
        mock_load.return_value = [
            {
                "protocol_id": 1,
                "content": "Colonoscopy clear liquid diet",
                "protocol": "Colonoscopy Preparation",
                "step": "Clear liquid diet",
                "instruction": "Follow the approved clear-liquid diet.",
                "minutes_before_procedure": 1440,
                "is_critical": True,
                "embedding": [1.0, 0.0],
            },
            {
                "protocol_id": 2,
                "content": "ECG clothing preparation",
                "protocol": "Routine ECG Preparation",
                "step": "Clothing preparation",
                "instruction": "Wear clothing that allows chest access.",
                "minutes_before_procedure": 60,
                "is_critical": False,
                "embedding": [1.0, 0.0],
            },
        ]

        mock_embed.return_value = [[1.0, 0.0]]

        results = retrieve_steps(
            "How do I follow the clear liquid diet?",
            protocol_id=1,
        )

        self.assertTrue(results)
        self.assertTrue(
            all(result["protocol_id"] == 1 for result in results)
        )
        self.assertTrue(
            all(
                result["protocol"] == "Colonoscopy Preparation"
                for result in results
            )
        )

    @patch("chatbot.rag._load_knowledge")
    @patch("chatbot.rag._embed_texts")
    def test_contextual_followup_retrieves_matching_stored_step(
        self,
        mock_embed,
        mock_load,
    ):
        mock_load.return_value = [
            {
                "protocol_id": 1,
                "content": "Colonoscopy fasting instruction",
                "protocol": "Colonoscopy Preparation",
                "step": "Fasting instruction",
                "instruction": (
                    "Stop eating only at the time specified in "
                    "your approved fasting instructions."
                ),
                "minutes_before_procedure": 480,
                "is_critical": True,
                "embedding": [1.0, 0.0],
            },
            {
                "protocol_id": 2,
                "content": "Water instruction",
                "protocol": "Other Procedure Preparation",
                "step": "Water instruction",
                "instruction": "Follow the water instructions for this procedure.",
                "minutes_before_procedure": 120,
                "is_critical": True,
                "embedding": [1.0, 0.0],
            },
        ]
        mock_embed.return_value = [[1.0, 0.0]]

        results = retrieve_steps(
            (
                "Earlier patient question: When should I stop eating? "
                "Current patient follow-up: And when?"
            ),
            protocol_id=1,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["protocol_id"], 1)
        self.assertEqual(results[0]["step"], "Fasting instruction")
        self.assertIn("approved fasting instructions", results[0]["instruction"])

    @patch("chatbot.rag._load_knowledge")
    @patch("chatbot.rag._embed_texts")
    def test_contextual_retrieval_never_returns_another_protocol(
        self,
        mock_embed,
        mock_load,
    ):
        mock_load.return_value = [
            {
                "protocol_id": 1,
                "content": "Fasting instruction",
                "protocol": "Protocol One",
                "step": "Fasting",
                "instruction": "Follow the stored fasting instruction.",
                "minutes_before_procedure": 480,
                "is_critical": True,
                "embedding": [1.0, 0.0],
            },
            {
                "protocol_id": 2,
                "content": "Fasting instruction",
                "protocol": "Protocol Two",
                "step": "Fasting",
                "instruction": "Different protocol instruction.",
                "minutes_before_procedure": 120,
                "is_critical": True,
                "embedding": [1.0, 0.0],
            },
        ]
        mock_embed.return_value = [[1.0, 0.0]]

        results = retrieve_steps(
            "Earlier patient question: fasting. Current patient follow-up: And when?",
            protocol_id=1,
        )

        self.assertTrue(results)
        self.assertTrue(
            all(result["protocol_id"] == 1 for result in results)
        )
        self.assertNotIn(
            "Different protocol instruction.",
            [result["instruction"] for result in results],
        )

    @patch("chatbot.rag.retrieve_steps")
    def test_contextual_followup_without_evidence_uses_safe_fallback(
        self,
        mock_retrieve,
    ):
        mock_retrieve.return_value = []

        result = answer_with_rag(
            "Earlier patient question: When should I stop eating? "
            "Current patient follow-up: And when?",
            protocol_id=1,
        )

        self.assertEqual(result["sources"], [])
        self.assertTrue(result["needs_clinical_team"])
        self.assertIn("couldn't confidently find", result["answer"])

    @patch("chatbot.rag.retrieve_steps")
    def test_contextual_medication_question_escalates_before_retrieval(
        self,
        mock_retrieve,
    ):
        result = answer_with_rag(
            "Earlier patient question: When should I stop eating? "
            "Current patient follow-up: Should I change my medication?",
            protocol_id=1,
        )

        self.assertTrue(result["needs_clinical_team"])
        self.assertEqual(result["sources"], [])
        self.assertIn("clinical team", result["answer"])
        mock_retrieve.assert_not_called()

    @patch("chatbot.rag.retrieve_steps")
    def test_contextual_exception_question_escalates_before_retrieval(
        self,
        mock_retrieve,
    ):
        result = answer_with_rag(
            "Earlier patient question: When should I stop eating? "
            "Current patient follow-up: What if I already ate?",
            protocol_id=1,
        )

        self.assertTrue(result["needs_clinical_team"])
        self.assertEqual(result["sources"], [])
        self.assertIn("clinical team", result["answer"])
        mock_retrieve.assert_not_called()

    @patch("chatbot.rag._load_knowledge")
    @patch("chatbot.rag._embed_texts")
    def test_unrelated_question_does_not_match_shared_procedure_name(
        self,
        mock_embed,
        mock_load,
    ):
        mock_load.return_value = [
            {
                "protocol_id": 1,
                "content": "Routine ECG Preparation",
                "protocol": "Routine ECG Preparation",
                "step": "During the ECG",
                "instruction": (
                    "Follow the technician's instructions, "
                    "lie still, and relax while the ECG recording is taken."
                ),
                "minutes_before_procedure": 10,
                "is_critical": False,
                "embedding": [1.0, 0.0],
            },
        ]
        mock_embed.return_value = [[0.8, 0.6]]

        results = retrieve_steps(
            "Can I drink coffee before my ECG?",
            protocol_id=1,
        )

        self.assertEqual(results, [])


    @patch("chatbot.rag._load_knowledge")
    @patch("chatbot.rag._embed_texts")
    def test_contextual_followup_rejects_unrelated_single_word_match(
        self,
        mock_embed,
        mock_load,
    ):
        mock_load.return_value = [
            {
                "protocol_id": 1,
                "content": "Fasting instruction",
                "protocol": "Colonoscopy Preparation",
                "protocol": "Colonoscopy Preparation",
                "step": "Fasting",
                "instruction": "Stop eating only at the time specified in your approved fasting instructions.",
                "minutes_before_procedure": 480,
                "is_critical": True,
                "embedding": [1.0, 0.0],
            },
            {
                "protocol_id": 1,
                "content": "Eating position instruction",
                "protocol": "Colonoscopy Preparation",
                "step": "During preparation",
                "instruction": "Avoid eating while walking to the clinic.",
                "minutes_before_procedure": 120,
                "is_critical": False,
                "embedding": [1.0, 0.0],
            },
        ]
        mock_embed.return_value = [[1.0, 0.0]]

        results = retrieve_steps(
            (
                "Earlier patient question: When should I stop eating? "
                "Current patient follow-up: And when?"
            ),
            protocol_id=1,
        )

        self.assertTrue(results)
        self.assertTrue(
            all(result["step"] == "Fasting" for result in results)
        )
