from django.test import SimpleTestCase

from chatbot.rag import safety_response


class HumanReviewSafetyTests(SimpleTestCase):
    def test_analysis_review_flag_escalates_even_without_keyword_match(self):
        result = safety_response("I need help with my preparation.", requires_human=True)
        self.assertIsNotNone(result)
        self.assertTrue(result["needs_clinical_team"])
        self.assertEqual(result["sources"], [])
        self.assertIn("clinical team", result["answer"].lower())

    def test_distress_review_is_not_dependent_on_emotion_prefix(self):
        result = safety_response("I feel overwhelmed.", requires_human=True)
        self.assertTrue(result["needs_clinical_team"])

    def test_existing_clinical_keyword_escalation_is_preserved(self):
        result = safety_response("I have chest pain.")
        self.assertTrue(result["needs_clinical_team"])

    def test_non_escalation_message_remains_eligible_for_rag(self):
        self.assertIsNone(safety_response("When should I arrive?"))
