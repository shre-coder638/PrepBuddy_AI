from django.test import SimpleTestCase
from types import SimpleNamespace

from .clarification import (
    assess_clarification,
    _has_object_reference,
    _has_object_mention,
)


def message(role, content):
    return SimpleNamespace(role=role, content=content)


class ClarificationTests(SimpleTestCase):

    def test_missing_procedure_requires_clarification(self):
        result = assess_clarification("What should I do before my scan?")

        self.assertTrue(result["required"])
        self.assertEqual(result["kind"], "procedure")

    def test_explicit_procedure_needs_no_procedure_clarification(self):
        result = assess_clarification("What should I know before my MRI?")

        self.assertFalse(result["required"])

    def test_multiple_procedures_require_clarification(self):
        result = assess_clarification(
            "I have an MRI and CT scan",
            active_protocol_id=14,
        )

        self.assertTrue(result["required"])
        self.assertEqual(result["kind"], "procedure")

    def test_active_protocol_supplies_missing_procedure_context(self):
        result = assess_clarification(
            "What should I do before the appointment?",
            active_protocol_id=14,
        )

        self.assertFalse(result["required"])

    def test_ambiguous_english_object_reference(self):
        result = assess_clarification(
            "Should I remove it?",
            active_protocol_id=14,
        )

        self.assertTrue(result["required"])
        self.assertEqual(result["kind"], "object")

    def test_ambiguous_english_this_reference_requires_clarification(self):
        result = assess_clarification(
            "Should I remove this?",
            active_protocol_id=14,
        )

        self.assertTrue(result["required"])
        self.assertEqual(result["kind"], "object")

    def test_ordinary_time_and_explanation_phrases_do_not_trigger_object_clarification(self):
        for question in (
            "Can I come this morning?",
            "What does that mean?",
        ):
            with self.subTest(question=question):
                result = assess_clarification(
                    question,
                    active_protocol_id=14,
                )
                self.assertFalse(result["required"])

    def test_named_english_object_needs_no_object_clarification(self):
        result = assess_clarification(
            "Should I remove my earrings?",
            active_protocol_id=14,
        )

        self.assertFalse(result["required"])

    def test_named_hindi_object_needs_no_object_clarification(self):
        result = assess_clarification(
            "Should I remove my " + "\u091a\u0947\u0928" + "?",
            active_protocol_id=14,
        )

        self.assertFalse(result["required"])

    def test_hindi_object_reference_requires_clarification(self):
        result = assess_clarification(
            "क्या मुझे इसे हटाना चाहिए?",
            active_protocol_id=14,
        )

        self.assertTrue(result["required"])
        self.assertEqual(result["kind"], "object")

    def test_hinglish_object_reference_requires_clarification(self):
        result = assess_clarification(
            "Kya isko remove karna hai?",
            active_protocol_id=14,
        )

        self.assertTrue(result["required"])
        self.assertEqual(result["kind"], "object")

    def test_recent_patient_object_mention_resolves_reference(self):
        history = [
            message("patient", "I wear a medication patch."),
            message("assistant", "I can check the stored instructions."),
        ]

        result = assess_clarification(
            "Should I remove it?",
            history=history,
            active_protocol_id=14,
        )

        self.assertFalse(result["required"])

    def test_old_unrelated_object_mention_does_not_resolve_reference(self):
        history = [
            message("patient", "I wear earrings."),
            message("assistant", "Let us discuss your appointment."),
            message("patient", "When should I arrive?"),
        ]

        result = assess_clarification(
            "Should I remove it?",
            history=history,
            active_protocol_id=14,
        )

        self.assertTrue(result["required"])
        self.assertEqual(result["kind"], "object")

    def test_assistant_object_mention_does_not_resolve_reference(self):
        history = [
            message("assistant", "You mentioned wearing earrings."),
        ]

        result = assess_clarification(
            "Should I remove it?",
            history=history,
            active_protocol_id=14,
        )

        self.assertTrue(result["required"])
        self.assertEqual(result["kind"], "object")

    def test_thank_you_acknowledgement_does_not_request_object_clarification(self):
        result = assess_clarification(
            "Thank you, that was helpful",
            active_protocol_id=14,
        )

        self.assertFalse(result["required"])
        self.assertIsNone(result["kind"])

    def test_empty_question_is_rejected(self):
        for question in ("", "   ", None):
            with self.subTest(question=question):
                with self.assertRaises(ValueError):
                    assess_clarification(question)

    def test_non_string_history_entries_are_ignored(self):
        history = [
            message("patient", None),
            message("patient", " "),
            message("assistant", "I mentioned a watch."),
        ]

        result = assess_clarification(
            "Should I remove it?",
            history=history,
            active_protocol_id=14,
        )

        self.assertTrue(result["required"])
        self.assertEqual(result["kind"], "object")

    def test_hindi_location_words_are_not_object_references(self):
        for phrase in (
            "\u092f\u0939\u093e\u0902",
            "\u0935\u0939\u093e\u0902",
        ):
            with self.subTest(phrase=phrase):
                self.assertFalse(_has_object_reference(phrase))

    def test_hindi_patchwork_is_not_a_medical_object_mention(self):
        self.assertFalse(
            _has_object_mention("\u092a\u0948\u091a\u0935\u0930\u094d\u0915")
        )

    def test_hindi_reference_and_object_terms_still_match(self):
        self.assertTrue(
            _has_object_reference("\u092e\u0941\u091d\u0947 \u0907\u0938\u0947 \u0939\u091f\u093e\u0928\u093e \u0939\u0948")
        )
        self.assertTrue(
            _has_object_mention("\u092e\u0947\u0930\u0940 \u091a\u0947\u0928")
        )

