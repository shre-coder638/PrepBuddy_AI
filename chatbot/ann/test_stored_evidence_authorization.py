import pytest

from chatbot.ann import remote_backend
from chatbot.ann.remote_client import RemoteANNError


def test_cloud_authorizes_stored_record_without_similarity(monkeypatch):
    record = {
        "protocol_id": 12,
        "protocol": "Synthetic Test Protocol",
        "step_id": 51,
        "step": "Confirm Test Appointment",
        "instruction": "Read the synthetic test notice.",
        "minutes_before_procedure": 60,
        "is_critical": False,
    }

    monkeypatch.setattr(
        remote_backend,
        "load_protocol_records",
        lambda protocol_id: [dict(record)],
    )

    response = {
        "answer": remote_backend.apply_communication_style(
            "Stored instruction - Confirm Test Appointment: "
            "Read the synthetic test notice.",
            "neutral",
        ),
        "sources": [{
            "protocol_id": 12,
            "protocol": record["protocol"],
            "step_id": 51,
            "step": record["step"],
            "minutes_before_procedure": 60,
            "is_critical": False,
        }],
        "needs_clinical_team": False,
    }

    result = remote_backend.validate_grounded_response(
        response,
        "Repeat Confirm Test Appointment",
        12,
        "neutral",
        expected_records=[record],
    )

    assert result == response

    for question in (
        "What if I missed my appointment?",
        "Repeat an unrelated instruction",
    ):
        with pytest.raises(
            RemoteANNError,
            match="Evidence authorization failed",
        ):
            remote_backend.validate_grounded_response(
                response,
                question,
                12,
                "neutral",
                expected_records=[record],
            )
