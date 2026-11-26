from copy import deepcopy
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from chatbot.ann.remote_backend import (
    answer_remote_ann,
    fallback,
)
from chatbot.ann.remote_client import RemoteANNError
from chatbot.response_generator import apply_communication_style
from chatbot.views import answer_question


PREFIX = "chatbot.ann.remote_backend."

QUESTION = "Repeat the Synthetic instruction"

RECORD = {
    "protocol_id": 101,
    "protocol": "Synthetic staging protocol",
    "protocol_description": "Software validation only",
    "step_id": 501,
    "step": "Synthetic instruction",
    "instruction": "This is a synthetic test record.",
    "minutes_before_procedure": 60,
    "order": 1,
    "is_critical": False,
    "requires_confirmation": False,
}

ANSWER = {
    "answer": apply_communication_style(
        "Stored instruction - Synthetic instruction: "
        "This is a synthetic test record.",
        "neutral",
    ),
    "sources": [{
        key: RECORD[key]
        for key in (
            "protocol_id",
            "protocol",
            "step_id",
            "step",
            "minutes_before_procedure",
            "is_critical",
        )
    }],
    "needs_clinical_team": False,
}


@override_settings(
    STAGING_MODE=True,
    CHATBOT_BACKEND="remote_ann",
    REMOTE_ANN_URL=(
        "https://ann.example.test/internal/ann/v1/answer/"
    ),
    ANN_SERVICE_TOKEN="synthetic_ann_service_token_" * 2,
)
class RemoteANNBackendTests(SimpleTestCase):

    def setUp(self):
        dependencies = {
            "request_remote_ann": deepcopy(ANSWER),
            "load_protocol_records": [deepcopy(RECORD)],
            "authorize_evidence": True,
            "assess_clarification": {"required": False},
            "is_preparation_overview": False,
        }

        for name, value in dependencies.items():
            patcher = patch(
                PREFIX + name,
                return_value=value,
            )

            mock = patcher.start()
            self.addCleanup(patcher.stop)
            setattr(self, name, mock)

    def invoke(self, **kwargs):
        arguments = {
            "question": QUESTION,
            "protocol_id": 101,
        }

        arguments.update(kwargs)

        return answer_remote_ann(**arguments)

    def test_grounded_answer(self):
        self.assertEqual(self.invoke(), ANSWER)
        self.load_protocol_records.assert_called_once_with(101)

        self.authorize_evidence.assert_called_once_with(
            QUESTION,
            RECORD,
            protocol_id=101,
        )

    def test_altered_instruction(self):
        result = deepcopy(ANSWER)
        result["answer"] = "Unsupported instruction."

        self.request_remote_ann.return_value = result

        self.assertEqual(self.invoke(), fallback())

    def test_wrong_protocol(self):
        result = deepcopy(ANSWER)
        result["sources"][0]["protocol_id"] = 102

        self.request_remote_ann.return_value = result

        self.assertEqual(self.invoke(), fallback())

    def test_wrong_step(self):
        result = deepcopy(ANSWER)
        result["sources"][0]["step_id"] = 999

        self.request_remote_ann.return_value = result

        self.assertEqual(self.invoke(), fallback())

    def test_changed_database_instruction(self):
        record = deepcopy(RECORD)
        record["instruction"] = "Updated synthetic test record."

        self.load_protocol_records.return_value = [record]

        self.assertEqual(self.invoke(), fallback())

    def test_unauthorized_evidence(self):
        self.authorize_evidence.return_value = False

        self.assertEqual(self.invoke(), fallback())

    def test_missing_database_record(self):
        self.load_protocol_records.return_value = []

        self.assertEqual(self.invoke(), fallback())

    def test_multiple_sources(self):
        result = deepcopy(ANSWER)
        result["sources"] *= 2

        self.request_remote_ann.return_value = result

        self.assertEqual(self.invoke(), fallback())

    def test_invalid_source_types(self):
        result = deepcopy(ANSWER)
        result["sources"][0]["is_critical"] = 0

        self.request_remote_ann.return_value = result

        self.assertEqual(self.invoke(), fallback())

    def test_unverified_answer_without_sources(self):
        self.request_remote_ann.return_value = {
            "answer": "Unverified remote text.",
            "sources": [],
            "needs_clinical_team": False,
        }

        self.assertEqual(self.invoke(), fallback())

    def test_unexpected_fields(self):
        result = deepcopy(ANSWER)
        result["unexpected"] = True

        self.request_remote_ann.return_value = result

        self.assertEqual(self.invoke(), fallback())

    def test_remote_unavailable(self):
        self.request_remote_ann.side_effect = RemoteANNError(
            "Synthetic network failure."
        )

        self.assertEqual(self.invoke(), fallback())

    def test_general_help_without_remote(self):
        result = self.invoke(
            question="Hello",
            protocol_id=None,
        )

        self.assertIn("Hello!", result["answer"])
        self.assertFalse(result["needs_clinical_team"])

        self.request_remote_ann.assert_not_called()

    def test_local_clinical_escalation(self):
        result = self.invoke(
            question="Can I change my medication?"
        )

        self.assertTrue(result["needs_clinical_team"])
        self.assertEqual(result["sources"], [])

        self.request_remote_ann.assert_not_called()

    def test_missing_protocol(self):
        result = self.invoke(protocol_id=None)

        self.assertTrue(result["needs_clinical_team"])
        self.request_remote_ann.assert_not_called()

    def test_qa_protocol_excluded(self):
        self.assertEqual(
            self.invoke(protocol_id=16),
            fallback(),
        )

        self.request_remote_ann.assert_not_called()

    def test_local_overview(self):
        self.is_preparation_overview.return_value = True

        with patch(
            PREFIX + "build_protocol_overview",
            return_value=ANSWER,
        ) as overview:
            result = self.invoke()

        self.assertEqual(result, ANSWER)
        overview.assert_called_once_with(
            101,
            communication_style="neutral",
        )

        self.request_remote_ann.assert_not_called()

    def test_local_clarification(self):
        self.assess_clarification.return_value = {
            "required": True,
            "kind": "procedure_mismatch",
            "message": "Synthetic clarification.",
        }

        result = self.invoke()

        self.assertTrue(result["needs_clinical_team"])
        self.assertEqual(
            result["answer"],
            "Synthetic clarification.",
        )

        self.request_remote_ann.assert_not_called()

    @override_settings(STAGING_MODE=False)
    def test_disabled_outside_staging(self):
        self.assertEqual(self.invoke(), fallback())
        self.request_remote_ann.assert_not_called()

    def test_main_dispatcher(self):
        self.assertEqual(
            answer_question(
                QUESTION,
                protocol_id=101,
            ),
            ANSWER,
        )
