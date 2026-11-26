"""Offline staging transport security tests."""

from unittest.mock import patch

import pytest
import requests

from notifications.staging_transport import post_staging_relay


URL = (
    "https://example.test"
    "/api/notifications/openwa/relay/send-text/"
)

HEADERS = {"X-Proxy-Token": "p" * 64}

PAYLOAD = {
    "chatId": "15550100101@c.us",
    "text": "Synthetic test",
}


def mock_response(factory, status, body):
    session = factory.return_value.__enter__.return_value

    response = (
        session.post.return_value.__enter__.return_value
    )

    response.status_code = status
    response.iter_content.return_value = [body]

    return session


def test_secure_transport():
    with patch(
        "notifications.staging_transport.requests.Session"
    ) as factory:
        session = mock_response(
            factory,
            200,
            b'{"success":true,"messageId":"synthetic"}',
        )

        result = post_staging_relay(
            URL, HEADERS, PAYLOAD,
        )

        assert result.status_code == 200
        assert result.json()["messageId"] == "synthetic"

        assert session.trust_env is False

        kwargs = session.post.call_args.kwargs

        assert kwargs["verify"] is True
        assert kwargs["allow_redirects"] is False
        assert kwargs["stream"] is True


@pytest.mark.parametrize("url", [
    URL.replace("https:", "http:"),
    URL + "?unexpected=1",
    URL + "#fragment",
    URL.replace("example.test", "user@example.test"),
    URL.replace("example.test", "example.test:8080"),
])
def test_invalid_relay_url(url):
    with patch(
        "notifications.staging_transport.requests.Session"
    ) as factory:

        with pytest.raises(requests.RequestException):
            post_staging_relay(url, HEADERS, PAYLOAD)

        factory.assert_not_called()


@pytest.mark.parametrize("status,body", [
    (301, b"{}"),
    (302, b"{}"),
    (200, b"{}"),
    (200, b"invalid JSON"),
    (200, b'{"success":false,"messageId":"test"}'),
    (200, b'{"success":true,"messageId":""}'),
    (200, b"x" * 17000),
])
def test_uncertain_acceptance(status, body):
    with patch(
        "notifications.staging_transport.requests.Session"
    ) as factory:
        mock_response(factory, status, body)

        with pytest.raises(requests.RequestException):
            post_staging_relay(URL, HEADERS, PAYLOAD)


@pytest.mark.parametrize("status", [401, 403, 409, 500, 503])
def test_upstream_error_preserved(status):
    with patch(
        "notifications.staging_transport.requests.Session"
    ) as factory:
        mock_response(factory, status, b"{}")

        result = post_staging_relay(
            URL, HEADERS, PAYLOAD,
        )

        assert result.status_code == status


def test_invalid_token():
    with patch(
        "notifications.staging_transport.requests.Session"
    ) as factory:

        with pytest.raises(requests.RequestException):
            post_staging_relay(URL, {}, PAYLOAD)

        factory.assert_not_called()
