from unittest.mock import Mock, patch
import json
import uuid

import pytest
from django.test import Client


RELAY_URL = "/api/notifications/openwa/relay/send-text/"


@pytest.fixture
def relay_client():
    return Client()


@pytest.fixture
def relay_settings(settings):
    settings.OPENWA_PROXY_TOKEN = "test-proxy-token"
    settings.OPENWA_API_KEY = "test-local-openwa-key"
    settings.OPENWA_BASE_URL = "http://127.0.0.1:2785"
    settings.OPENWA_SESSION_ID = "test-session-id"
    return settings


def relay_post(client, payload=None, token="test-proxy-token",
               idempotency_key=None, content_type="application/json",
               raw_data=None):
    headers = {"HTTP_X_PROXY_TOKEN": token}

    if idempotency_key is not None:
        headers["HTTP_IDEMPOTENCY_KEY"] = idempotency_key

    if raw_data is not None:
        data = raw_data
    else:
        data = json.dumps(payload if payload is not None else {
            "chatId": "919876543210@c.us",
            "text": "Test message",
        })

    return client.post(
        RELAY_URL,
        data=data,
        content_type=content_type,
        **headers,
    )


def test_relay_rejects_missing_proxy_token(relay_client, relay_settings):
    response = relay_post(relay_client, token="")

    assert response.status_code == 401


def test_relay_rejects_invalid_proxy_token(relay_client, relay_settings):
    with patch("notifications.views.requests.post") as mock_post:
        response = relay_post(relay_client, token="wrong-token")

    assert response.status_code == 401
    mock_post.assert_not_called()


def test_relay_rejects_unconfigured_proxy_token(relay_client, relay_settings):
    relay_settings.OPENWA_PROXY_TOKEN = ""

    response = relay_post(relay_client)

    assert response.status_code == 503


def test_relay_rejects_non_post_method(relay_client, relay_settings):
    response = relay_client.get(
        RELAY_URL,
        HTTP_X_PROXY_TOKEN="test-proxy-token",
    )

    assert response.status_code == 405


@pytest.mark.parametrize(
    "payload",
    [
        {"chatId": "919876543210@c.us"},
        {"text": "Test message"},
        {"chatId": "", "text": "Test message"},
        {"chatId": "919876543210@c.us", "text": ""},
        {"chatId": "919876543210@c.us", "text": "Test message", "extra": 1},
    ],
)
def test_relay_rejects_invalid_payload(
    relay_client, relay_settings, payload
):
    response = relay_post(
        relay_client,
        payload=payload,
        idempotency_key=str(uuid.uuid4()),
    )

    assert response.status_code == 400


def test_relay_rejects_invalid_json(relay_client, relay_settings):
    response = relay_post(
        relay_client,
        raw_data=b"{invalid-json",
        idempotency_key=str(uuid.uuid4()),
    )

    assert response.status_code == 400


def test_relay_rejects_wrong_content_type(relay_client, relay_settings):
    response = relay_post(
        relay_client,
        content_type="text/plain",
        idempotency_key=str(uuid.uuid4()),
    )

    assert response.status_code == 415


def test_relay_requires_valid_idempotency_key(
    relay_client, relay_settings
):
    response = relay_post(relay_client, idempotency_key="not-a-uuid")

    assert response.status_code == 400


def test_relay_forwards_authenticated_request_to_local_openwa(
    relay_client, relay_settings
):
    idempotency_key = str(uuid.uuid4())
    upstream_response = Mock(
        status_code=202,
        content=b'{"messageId":"test-message-id"}',
    )

    with patch(
        "notifications.views.requests.post",
        return_value=upstream_response,
    ) as mock_post:
        response = relay_post(
            relay_client,
            idempotency_key=idempotency_key,
        )

    assert response.status_code == 202
    assert response.content == upstream_response.content

    mock_post.assert_called_once_with(
        "http://127.0.0.1:2785/api/sessions/test-session-id/messages/send-text",
        headers={
            "X-API-Key": "test-local-openwa-key",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        },
        json={
            "chatId": "919876543210@c.us",
            "text": "Test message",
        },
        timeout=15,
    )


def test_relay_returns_502_when_local_openwa_is_unavailable(
    relay_client, relay_settings
):
    import requests

    with patch(
        "notifications.views.requests.post",
        side_effect=requests.ConnectionError("connection failed"),
    ):
        response = relay_post(
            relay_client,
            idempotency_key=str(uuid.uuid4()),
        )

    assert response.status_code == 502
