"""Tests for database-independent E5 inference."""

from unittest.mock import Mock

import numpy as np
import pytest

from chatbot.ann import e5_retrieval


def record(step_id=51, protocol_id=12, text="Appointment"):
    return {
        "protocol_id": protocol_id,
        "step_id": step_id,
        "text": text,
    }


@pytest.fixture
def blocked_database(monkeypatch):
    from chatbot.evaluation import load_protocols

    loader = Mock(
        side_effect=AssertionError(
            "Unexpected database corpus access"
        )
    )

    monkeypatch.setattr(
        load_protocols,
        "load_active_protocols",
        loader,
    )

    yield loader

    loader.assert_not_called()


@pytest.fixture
def fake_model(monkeypatch):
    model = Mock()

    def encode(texts, **kwargs):
        return np.array([
            [1.0, 0.0]
            if text.startswith("query:") or "Appointment" in text
            else [0.0, 1.0]
            for text in texts
        ])

    model.encode.side_effect = encode

    monkeypatch.setattr(
        e5_retrieval,
        "_get_model",
        lambda: model,
    )

    monkeypatch.setattr(
        e5_retrieval,
        "_cached_fingerprint",
        None,
    )

    monkeypatch.setattr(
        e5_retrieval,
        "_cached_passage_vectors",
        None,
    )

    return model


def test_supplied_corpus_retrieval(
    blocked_database,
    fake_model,
):
    results = e5_retrieval.retrieve_e5_steps(
        "Confirm my appointment",
        protocol_id=12,
        corpus_records=[
            record(58, text="Bring documents"),
            record(51, text="Appointment"),
        ],
        limit=1,
    )

    assert len(results) == 1
    assert results[0]["protocol_id"] == 12
    assert results[0]["step_id"] == 51
    assert results[0]["similarity"] == pytest.approx(1.0)


def test_empty_corpus_does_not_load_model_or_database(
    blocked_database,
    fake_model,
):
    results = e5_retrieval.retrieve_e5_steps(
        "Appointment",
        protocol_id=12,
        corpus_records=[],
    )

    assert results == []
    fake_model.encode.assert_not_called()


@pytest.mark.parametrize(
    "records",
    [
        [record(protocol_id=13)],
        [record(protocol_id=True)],
        [record(step_id=True)],
        [record(step_id=0)],
        [record(), record()],
        [record(text="")],
        [record(text="   ")],
        [record(text=None)],
        [record(text="Invalid\x00text")],
        [None],
        {"invalid": "corpus"},
    ],
)
def test_invalid_supplied_corpus_rejected(
    records,
    blocked_database,
    fake_model,
):
    with pytest.raises(ValueError):
        e5_retrieval.retrieve_e5_steps(
            "Appointment",
            protocol_id=12,
            corpus_records=records,
        )

    fake_model.encode.assert_not_called()


def test_supplied_corpus_requires_protocol(
    blocked_database,
    fake_model,
):
    with pytest.raises(ValueError):
        e5_retrieval.retrieve_e5_steps(
            "Appointment",
            corpus_records=[record()],
        )


def test_embedding_cache_refreshes_after_instruction_change(
    blocked_database,
    fake_model,
):
    def retrieve(text):
        return e5_retrieval.retrieve_e5_steps(
            "Appointment",
            protocol_id=12,
            corpus_records=[record(text=text)],
        )

    first = retrieve("Appointment original")
    second = retrieve("Appointment original")
    third = retrieve("Appointment updated")

    assert first[0]["text"] == "Appointment original"
    assert second[0]["text"] == "Appointment original"
    assert third[0]["text"] == "Appointment updated"

    passage_calls = [
        call
        for call in fake_model.encode.call_args_list
        if call.args[0][0].startswith("passage:")
    ]

    assert len(passage_calls) == 2


def test_retrieval_does_not_mutate_supplied_records(
    blocked_database,
    fake_model,
):
    records = [record()]

    e5_retrieval.retrieve_e5_steps(
        "Appointment",
        protocol_id=12,
        corpus_records=records,
    )

    assert "similarity" not in records[0]
