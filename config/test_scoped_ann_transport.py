"""Regression tests for database-independent ANN transport."""

import json

from copy import deepcopy
from unittest.mock import Mock, patch

import pytest
from django.test import Client

from chatbot.ann import remote_backend
from chatbot.ann.remote_client import (
    request_scoped_ann,
    RemoteANNError,
)
from chatbot.ann.remote_protocol import (
    MAX_SCOPED_BODY_BYTES,
    validate_scoped_payload,
)


URL = "/internal/ann/v2/answer/"
HTTPS_URL = "https://ann.example.test" + URL
TOKEN = "a" * 64


RECORD = {
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
}


ANSWER = {
    "answer": (
        "Stored instruction - Synthetic instruction: "
        "This is a synthetic test record."
    ),
    "sources": [{
        "protocol_id": 1,
        "protocol": "Synthetic Staging Protocol",
        "step_id": 1,
        "step": "Synthetic instruction",
        "minutes_before_procedure": 60,
        "is_critical": False,
    }],
    "needs_clinical_team": False,
}


@pytest.fixture
def payload():
    return {
        "question": "Repeat the Synthetic instruction",
        "protocol_id": 1,
        "protocol_records": [deepcopy(RECORD)],
        "communication_style": "neutral",
        "requires_human": False,
    }


@pytest.fixture
def scoped_client(settings):
    settings.ROOT_URLCONF = "config.ann_service_urls"
    settings.ANN_SERVICE_TOKEN = TOKEN
    settings.ALLOWED_HOSTS = ["testserver"]
    settings.MIDDLEWARE = []
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_SCOPED_BODY_BYTES

    return Client()


def post(client, payload, token=TOKEN):
    return client.post(
        URL,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer " + token,
    )


def test_scoped_endpoint_success(scoped_client, payload):
    with patch(
        "chatbot.ann.remote_protocol.invoke_scoped_ann",
        return_value=deepcopy(ANSWER),
    ) as inference:
        response = post(scoped_client, payload)

    assert response.status_code == 200
    assert response.json() == ANSWER
    assert response["Cache-Control"] == "no-store"

    inference.assert_called_once_with(**payload)


def test_scoped_endpoint_requires_auth(scoped_client, payload):
    response = post(scoped_client, payload, token="invalid")

    assert response.status_code == 401


def test_scoped_endpoint_rejects_missing_records(
    scoped_client,
    payload,
):
    del payload["protocol_records"]

    with patch(
        "chatbot.ann.remote_protocol.invoke_scoped_ann"
    ) as inference:
        response = post(scoped_client, payload)

    assert response.status_code == 400
    inference.assert_not_called()


def test_scoped_endpoint_rejects_wrong_protocol(
    scoped_client,
    payload,
):
    payload["protocol_records"][0]["protocol_id"] = 12

    assert post(scoped_client, payload).status_code == 400


def test_scoped_endpoint_rejects_large_body(scoped_client):
    response = scoped_client.post(
        URL,
        data="a" * (MAX_SCOPED_BODY_BYTES + 1),
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer " + TOKEN,
    )

    assert response.status_code == 413


@pytest.mark.parametrize("body", [
    '{"question":"one","question":"two"}',
    '{"question":NaN}',
    '{"question":Infinity}',
])
def test_scoped_endpoint_rejects_invalid_json(
    scoped_client,
    body,
):
    response = scoped_client.post(
        URL,
        data=body,
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer " + TOKEN,
    )

    assert response.status_code == 400


def test_negative_preparation_minutes_rejected(payload):
    payload["protocol_records"][0][
        "minutes_before_procedure"
    ] = -1

    with pytest.raises(ValueError):
        validate_scoped_payload(payload)


def test_scoped_https_client(payload):
    with patch(
        "chatbot.ann.remote_client._post_remote_ann",
        return_value=deepcopy(ANSWER),
    ) as transport:

        result = request_scoped_ann(
            url=HTTPS_URL,
            token=TOKEN,
            **payload,
        )

    assert result == ANSWER

    url, token, body = transport.call_args.args

    assert url == HTTPS_URL
    assert token == TOKEN
    assert json.loads(body.decode("utf-8")) == payload


@pytest.mark.parametrize("url", [
    "http://ann.example.test" + URL,
    "https://ann.example.test/internal/ann/v1/answer/",
    HTTPS_URL + "?unexpected=true",
])
def test_scoped_client_rejects_invalid_urls(payload, url):
    with patch(
        "chatbot.ann.remote_client._post_remote_ann"
    ) as transport:

        with pytest.raises(RemoteANNError):
            request_scoped_ann(
                url=url,
                token=TOKEN,
                **payload,
            )

    transport.assert_not_called()


def test_scoped_client_rejects_oversized_payload(payload):
    payload["protocol_records"] = [
        dict(
            RECORD,
            step_id=index,
            instruction="a" * 8192,
        )
        for index in range(1, 21)
    ]

    with patch(
        "chatbot.ann.remote_client._post_remote_ann"
    ) as transport:

        with pytest.raises(RemoteANNError):
            request_scoped_ann(
                url=HTTPS_URL,
                token=TOKEN,
                **payload,
            )

    transport.assert_not_called()


@pytest.fixture
def cloud(settings, monkeypatch):
    settings.STAGING_MODE = True
    settings.CHATBOT_BACKEND = "remote_ann"
    settings.REMOTE_ANN_URL = HTTPS_URL
    settings.ANN_SERVICE_TOKEN = TOKEN

    loader = Mock(return_value=[deepcopy(RECORD)])
    scoped = Mock(return_value=deepcopy(ANSWER))
    legacy = Mock(
        side_effect=AssertionError("Unexpected legacy request")
    )

    monkeypatch.setattr(
        remote_backend,
        "load_protocol_records",
        loader,
    )

    monkeypatch.setattr(
        remote_backend,
        "request_scoped_ann",
        scoped,
    )

    monkeypatch.setattr(
        remote_backend,
        "request_remote_ann",
        legacy,
    )

    monkeypatch.setattr(
        remote_backend,
        "authorize_stored_evidence",
        Mock(return_value=True),
    )

    yield loader, scoped

    legacy.assert_not_called()


def answer():
    return remote_backend.answer_remote_ann(
        "Repeat the Synthetic instruction",
        protocol_id=1,
    )


def test_cloud_dispatch_and_revalidation(cloud):
    loader, scoped = cloud

    assert answer() == ANSWER

    assert loader.call_count == 2

    scoped.assert_called_once_with(
        url=HTTPS_URL,
        token=TOKEN,
        question="Repeat the Synthetic instruction",
        protocol_id=1,
        protocol_records=[RECORD],
        communication_style="neutral",
        requires_human=False,
    )


def test_cloud_rejects_changed_protocol_snapshot(cloud):
    loader, scoped = cloud

    changed = dict(
        RECORD,
        instruction="Updated synthetic instruction.",
    )

    loader.side_effect = [
        [deepcopy(RECORD)],
        [changed],
    ]

    result = answer()

    assert result["sources"] == []
    assert result["needs_clinical_team"] is True


def test_cloud_rejects_new_protocol_step(cloud):
    loader, scoped = cloud

    added = dict(RECORD, step_id=2)

    loader.side_effect = [
        [deepcopy(RECORD)],
        [deepcopy(RECORD), added],
    ]

    result = answer()

    assert result["sources"] == []
    assert result["needs_clinical_team"] is True


def test_cloud_does_not_send_empty_protocol(cloud):
    loader, scoped = cloud

    loader.return_value = []

    assert answer()["sources"] == []
    scoped.assert_not_called()


def test_cloud_remote_failure_does_not_use_legacy(cloud):
    loader, scoped = cloud

    scoped.side_effect = RemoteANNError(
        "Synthetic connectivity failure"
    )

    result = answer()

    assert result["sources"] == []
    assert result["needs_clinical_team"] is True
