"""Security and compatibility tests for scoped ANN transport."""

from copy import deepcopy
from unittest.mock import Mock

import numpy as np
import pytest

from chatbot.ann import backend, e5_retrieval
from chatbot.ann import protocol_overview
from chatbot.ann.remote_protocol import (
    invoke_scoped_ann,
    validate_scoped_payload,
)


@pytest.fixture
def payload():
    return {
        "question": "Repeat the Synthetic instruction",
        "protocol_id": 1,
        "communication_style": "neutral",
        "requires_human": False,
        "protocol_records": [{
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
        }],
    }


def test_valid_payload(payload):
    original = deepcopy(payload)
    validated = validate_scoped_payload(payload)

    assert validated == original
    assert payload == original

    assert (
        validated["protocol_records"][0]
        is not payload["protocol_records"][0]
    )


def test_missing_records(payload):
    del payload["protocol_records"]

    with pytest.raises(ValueError):
        validate_scoped_payload(payload)


def test_empty_records_are_explicit(payload):
    payload["protocol_records"] = []

    assert (
        validate_scoped_payload(payload)["protocol_records"]
        == []
    )


@pytest.mark.parametrize("protocol_id", [
    None, True, 0, -1, "1", 9223372036854775808,
])
def test_invalid_protocol_id(payload, protocol_id):
    payload["protocol_id"] = protocol_id

    with pytest.raises(ValueError):
        validate_scoped_payload(payload)


@pytest.mark.parametrize("field,value", [
    ("protocol_id", 12),
    ("protocol_id", True),
    ("step_id", True),
    ("step_id", 0),
    ("step_id", -1),
    ("protocol", ""),
    ("protocol", "a" * 257),
    ("protocol_description", None),
    ("protocol_description", "a" * 4097),
    ("step", ""),
    ("step", "a" * 257),
    ("instruction", ""),
    ("instruction", "."),
    ("instruction", "N/A"),
    ("instruction", "a" * 8193),
    ("instruction", "Invalid\x00text"),
    ("instruction", "\ud800"),
    ("minutes_before_procedure", True),
    ("minutes_before_procedure", "60"),
    ("order", -1),
    ("order", True),
    ("is_critical", 1),
    ("requires_confirmation", "false"),
])
def test_invalid_record_fields(payload, field, value):
    payload["protocol_records"][0][field] = value

    with pytest.raises(ValueError):
        validate_scoped_payload(payload)


def test_duplicate_step_ids(payload):
    payload["protocol_records"].append(
        deepcopy(payload["protocol_records"][0])
    )

    with pytest.raises(ValueError):
        validate_scoped_payload(payload)


def test_too_many_records(payload):
    record = payload["protocol_records"][0]

    payload["protocol_records"] = [
        dict(record, step_id=index)
        for index in range(1, 66)
    ]

    with pytest.raises(ValueError):
        validate_scoped_payload(payload)


def test_inconsistent_metadata(payload):
    second = dict(
        payload["protocol_records"][0],
        step_id=2,
        protocol="Different protocol name",
    )

    payload["protocol_records"].append(second)

    with pytest.raises(ValueError):
        validate_scoped_payload(payload)


def test_unexpected_record_field(payload):
    payload["protocol_records"][0]["text"] = (
        "Untrusted embedding passage"
    )

    with pytest.raises(ValueError):
        validate_scoped_payload(payload)


def test_unexpected_top_level_field(payload):
    payload["patient_phone"] = "synthetic"

    with pytest.raises(ValueError):
        validate_scoped_payload(payload)


def test_missing_record_field(payload):
    del payload["protocol_records"][0]["instruction"]

    with pytest.raises(ValueError):
        validate_scoped_payload(payload)


@pytest.mark.parametrize("records", [
    None,
    {},
    "invalid",
    [None],
])
def test_invalid_record_collection(payload, records):
    payload["protocol_records"] = records

    with pytest.raises(ValueError):
        validate_scoped_payload(payload)


def test_grounded_inference_without_database(
    payload,
    monkeypatch,
    settings,
):
    from chatbot.evaluation import load_protocols

    settings.CHATBOT_BACKEND = "ann"

    # Even if telemetry is enabled elsewhere, scoped
    # inference must not record database experiences.
    settings.ANN_RECORD_EXPERIENCES = True

    blocked = Mock(
        side_effect=AssertionError(
            "Unexpected database operation"
        )
    )

    monkeypatch.setattr(
        load_protocols,
        "load_active_protocols",
        blocked,
    )

    monkeypatch.setattr(
        protocol_overview,
        "load_protocol_records",
        blocked,
    )

    monkeypatch.setattr(
        backend,
        "record_experience",
        blocked,
    )

    model = Mock()

    model.encode.side_effect = (
        lambda texts, **kwargs:
        np.array([[1.0, 0.0] for _ in texts])
    )

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

    result = invoke_scoped_ann(
        **validate_scoped_payload(payload)
    )

    blocked.assert_not_called()

    assert result["needs_clinical_team"] is False
    assert len(result["sources"]) == 1
    assert result["sources"][0]["protocol_id"] == 1
    assert result["sources"][0]["step_id"] == 1

    assert (
        payload["protocol_records"][0]["instruction"]
        in result["answer"]
    )
