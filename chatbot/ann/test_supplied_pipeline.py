"""Database-independent ANN pipeline regression tests."""

from unittest.mock import Mock

import pytest

from chatbot.ann import pipeline, protocol_overview
from chatbot.ann import e5_retrieval
from chatbot.ann.protocol_records import build_retrieval_corpus


@pytest.fixture
def records():
    return [{
        "protocol_id": 1,
        "protocol": "Synthetic Staging Protocol",
        "protocol_description": "Software testing only.",
        "step_id": 1,
        "step": "Synthetic instruction",
        "instruction": "This is a synthetic test record.",
        "minutes_before_procedure": 60,
        "order": 1,
        "is_critical": False,
        "requires_confirmation": False,
    }]


@pytest.fixture
def blocked_database(monkeypatch):
    from chatbot.evaluation import load_protocols

    loader = Mock(
        side_effect=AssertionError(
            "Unexpected database access"
        )
    )

    monkeypatch.setattr(
        load_protocols,
        "load_active_protocols",
        loader,
    )

    monkeypatch.setattr(
        protocol_overview,
        "load_protocol_records",
        loader,
    )

    yield loader

    loader.assert_not_called()


def test_canonical_corpus_format(records):
    corpus = build_retrieval_corpus(records)

    assert corpus[0]["text"] == (
        "Protocol ID: 1\n"
        "Procedure: Synthetic Staging Protocol\n"
        "Protocol description: Software testing only.\n"
        "Step: Synthetic instruction\n"
        "Instruction: This is a synthetic test record."
    )

    assert corpus[0]["step_id"] == 1
    assert "text" not in records[0]


def test_empty_corpus_builder():
    assert build_retrieval_corpus([]) == []


def test_pipeline_forwards_supplied_corpus(
    monkeypatch,
    records,
    blocked_database,
):
    corpus = build_retrieval_corpus(records)
    retrieve = Mock(return_value=[])

    monkeypatch.setattr(
        pipeline,
        "retrieve_e5_steps",
        retrieve,
    )

    question = "Repeat the Synthetic instruction"

    result = pipeline.answer_with_ann(
        question,
        protocol_id=1,
        corpus_records=corpus,
    )

    retrieve.assert_called_once_with(
        question,
        protocol_id=1,
        limit=10,
        corpus_records=corpus,
    )

    assert result["sources"] == []
    assert result["needs_clinical_team"] is True


def test_empty_pipeline_corpus_never_loads_database(
    monkeypatch,
    blocked_database,
):
    model_loader = Mock(
        side_effect=AssertionError(
            "Unexpected model initialization"
        )
    )

    monkeypatch.setattr(
        e5_retrieval,
        "_get_model",
        model_loader,
    )

    trace = {}

    result = pipeline.answer_with_ann(
        "Repeat the Synthetic instruction",
        protocol_id=1,
        corpus_records=[],
        trace=trace,
    )

    assert result["sources"] == []
    assert result["needs_clinical_team"] is True
    assert trace["outcome"] == "abstention"

    model_loader.assert_not_called()


def test_supplied_protocol_overview(
    records,
    blocked_database,
):
    result = protocol_overview.build_protocol_overview(
        1,
        corpus_records=records,
    )

    assert result is not None
    assert result["needs_clinical_team"] is False
    assert result["sources"][0]["step_id"] == 1
    assert records[0]["instruction"] in result["answer"]


def test_empty_supplied_overview(blocked_database):
    assert protocol_overview.build_protocol_overview(
        1,
        corpus_records=[],
    ) is None


def test_cross_protocol_overview_rejected(
    records,
    blocked_database,
):
    assert protocol_overview.build_protocol_overview(
        12,
        corpus_records=records,
    ) is None


def test_pipeline_overview_uses_supplied_records(
    monkeypatch,
    records,
    blocked_database,
):
    monkeypatch.setattr(
        pipeline,
        "is_preparation_overview",
        lambda question: True,
    )

    result = pipeline.answer_with_ann(
        "Repeat the Synthetic instruction",
        protocol_id=1,
        corpus_records=build_retrieval_corpus(records),
    )

    assert result["needs_clinical_team"] is False
    assert result["sources"][0]["step_id"] == 1
    assert records[0]["instruction"] in result["answer"]
