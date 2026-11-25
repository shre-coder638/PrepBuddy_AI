from unittest.mock import patch

from django.test import override_settings

from chatbot.views import answer_question
from chatbot.ann.backend import answer_configured_ann
from chatbot.rag import SAFE_FALLBACK


MODULE = "chatbot.ann.backend"

RESULT = {
    "answer": "Synthetic preparation instruction.",
    "sources": [],
    "needs_clinical_team": False,
}


@override_settings(CHATBOT_BACKEND="rag")
def test_legacy_compatibility():

    with patch(
        "chatbot.views.answer_with_rag",
        return_value=RESULT,
    ) as legacy:

        result = answer_question(
            "Hello",
            protocol_id=14,
        )

    assert result == RESULT
    legacy.assert_called_once()


@override_settings(
    CHATBOT_BACKEND="ann",
    ANN_RECORD_EXPERIENCES=False,
)
def test_ann_routing():

    with (
        patch(
            MODULE + ".answer_with_ann",
            return_value=RESULT,
        ) as ann,
        patch(
            "chatbot.views.answer_with_rag",
        ) as legacy,
        patch(
            MODULE + ".record_experience",
        ) as recorder,
    ):

        result = answer_question(
            "Synthetic question",
            protocol_id=14,
        )

    assert result == RESULT

    ann.assert_called_once()
    assert ann.call_args.kwargs["protocol_id"] == 14

    legacy.assert_not_called()
    recorder.assert_not_called()


@override_settings(
    CHATBOT_BACKEND="ann",
    ANN_RECORD_EXPERIENCES=True,
)
def test_experience_recording():

    def synthetic_answer(*args, **kwargs):

        kwargs["trace"].update(
            outcome="grounded",
            retrieved_step_ids=[79, 80],
        )

        return {
            "answer": "Synthetic instruction.",
            "sources": [{"step_id": 79}],
            "needs_clinical_team": False,
        }

    with (
        patch(
            MODULE + ".answer_with_ann",
            side_effect=synthetic_answer,
        ),
        patch(
            MODULE + ".record_experience",
        ) as recorder,
    ):

        result = answer_configured_ann(
            "Synthetic question",
            protocol_id=14,
        )

    recorder.assert_called_once()

    recorded = recorder.call_args.kwargs

    assert recorded["outcome"] == "grounded"
    assert recorded["retrieved_step_ids"] == [79, 80]
    assert recorded["returned_step_ids"] == [79]

    assert "question" not in recorded
    assert "answer" not in recorded

    assert result["sources"][0]["step_id"] == 79


@override_settings(
    CHATBOT_BACKEND="ann",
    ANN_RECORD_EXPERIENCES=True,
)
def test_recording_failure_preserves_answer():

    with (
        patch(
            MODULE + ".answer_with_ann",
            return_value=RESULT,
        ),
        patch(
            MODULE + ".record_experience",
            side_effect=RuntimeError("Synthetic failure"),
        ),
    ):

        result = answer_configured_ann(
            "Synthetic question",
        )

    assert result == RESULT


@override_settings(
    CHATBOT_BACKEND="ann",
    ANN_RECORD_EXPERIENCES=False,
)
def test_ann_failure_abstains():

    with (
        patch(
            MODULE + ".answer_with_ann",
            side_effect=RuntimeError("Synthetic failure"),
        ),
        patch(
            "chatbot.views.answer_with_rag",
        ) as legacy,
    ):

        result = answer_question(
            "Synthetic question",
            protocol_id=14,
        )

    assert result["answer"] == SAFE_FALLBACK
    assert result["sources"] == []
    assert result["needs_clinical_team"] is True

    legacy.assert_not_called()


@override_settings(CHATBOT_BACKEND="invalid")
def test_invalid_configuration_abstains():

    with patch(
        MODULE + ".answer_with_ann",
    ) as ann:

        result = answer_question(
            "Synthetic question",
            protocol_id=14,
        )

    assert result["needs_clinical_team"] is True
    ann.assert_not_called()


import pytest

from chatbot.models import ANNExperience, ANNReviewedExample


@pytest.mark.django_db
@override_settings(
    CHATBOT_BACKEND="ann",
    ANN_RECORD_EXPERIENCES=True,
)
def test_real_persistent_ann_experience():

    assert ANNExperience.objects.count() == 0

    result = answer_question("Hello")

    assert result["sources"] == []
    assert result["needs_clinical_team"] is False

    experience = ANNExperience.objects.get()

    assert experience.outcome == "general_help"
    assert experience.model_version == "e5-pipeline-v1"
    assert experience.protocol_id is None
    assert experience.retrieved_step_ids == []
    assert experience.returned_step_ids == []
    assert experience.latency_ms >= 0

    assert ANNReviewedExample.objects.count() == 0

