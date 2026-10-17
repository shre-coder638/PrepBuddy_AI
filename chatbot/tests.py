
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
    def test_answer_uses_retrieved_evidence(
        self,
        mock_post,
        mock_retrieve,
    ):
        mock_retrieve.return_value = [
            {
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

        mock_post.return_value.json.return_value = {
            "message": {
                "content": (
                    "The stored instruction says to transition to "
                    "the approved clear-liquid diet before the procedure."
                )
            }
        }
        mock_post.return_value.raise_for_status.return_value = None

        result = answer_with_rag("What does my stored instruction say?")

        self.assertIn("clear-liquid diet", result["answer"])
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(
            result["sources"][0]["step"],
            "Avoid solid foods",
        )
        self.assertFalse(result["needs_clinical_team"])

        sent_payload = mock_post.call_args.kwargs["json"]
        prompt = sent_payload["messages"][0]["content"]
        self.assertIn("Avoid solid foods", prompt)
        self.assertIn("ONLY the evidence", prompt)

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
                "content": "clear liquid diet",
                "protocol": "Colonoscopy Preparation",
                "step": "Avoid solid foods",
                "instruction": "Use the approved clear-liquid diet.",
                "minutes_before_procedure": 180,
                "is_critical": True,
                "embedding": [1.0, 0.0],
            },
            {
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
