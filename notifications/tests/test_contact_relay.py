"""Offline tests for hybrid OpenWA contact resolution."""

from unittest.mock import MagicMock, patch

import pytest

from notifications.contact_relay import resolve_contact_via_relay


URL = (
    "https://example.test"
    "/api/notifications/openwa/relay/resolve-contact/"
)


@pytest.fixture
def relay_settings(settings):
    settings.OPENWA_CONTACT_RELAY_URL = URL
    settings.OPENWA_PROXY_TOKEN = "p" * 64
    return settings


def mock_session(factory, status=200, body=b"{}"):
    session = factory.return_value.__enter__.return_value

    response = (
        session.post.return_value.__enter__.return_value
    )

    response.status_code = status
    response.iter_content.return_value = [body]

    return session


def test_valid_contact_resolution(relay_settings):
    with patch(
        "notifications.contact_relay.requests.Session"
    ) as factory:

        session = mock_session(
            factory,
            body=b'{"phone":"+919999999999"}',
        )

        result = resolve_contact_via_relay("123456789@lid")

        assert result == {"phone": "919999999999"}

        assert session.trust_env is False

        kwargs = session.post.call_args.kwargs

        assert kwargs["verify"] is True
        assert kwargs["allow_redirects"] is False
        assert kwargs["json"] == {
            "chatId": "123456789@lid"
        }


@pytest.mark.parametrize("sender", [
    "",
    "123@g.us",
    "../contacts",
    "123@newsletter",
    "123@lid?test=1",
])
def test_invalid_sender(relay_settings, sender):
    with patch(
        "notifications.contact_relay.requests.Session"
    ) as factory:

        with pytest.raises(ValueError):
            resolve_contact_via_relay(sender)

        factory.assert_not_called()


@pytest.mark.parametrize("url", [
    URL.replace("https:", "http:"),
    URL + "?test=1",
    URL + "#fragment",
    URL.replace("example.test", "user@example.test"),
    URL.replace("example.test", "example.test:8080"),
    "https://example.test/",
])
def test_invalid_url(relay_settings, url):
    relay_settings.OPENWA_CONTACT_RELAY_URL = url

    with patch(
        "notifications.contact_relay.requests.Session"
    ) as factory:

        with pytest.raises(ValueError):
            resolve_contact_via_relay("123@lid")

        factory.assert_not_called()


@pytest.mark.parametrize("body", [
    b"[]",
    b"{}",
    b'{"phone":"abc"}',
    b'{"phone":"123"}',
    b'{"phone":1234567890}',
    b'{"phone":"919999999999","extra":true}',
    b"x" * 5000,
])
def test_invalid_contact_response(relay_settings, body):
    with patch(
        "notifications.contact_relay.requests.Session"
    ) as factory:

        mock_session(factory, body=body)

        with pytest.raises(ValueError):
            resolve_contact_via_relay("123@lid")


@pytest.mark.parametrize("status", [
    301, 302, 401, 403, 404, 500, 503,
])
def test_unsuccessful_contact_response(
    relay_settings,
    status,
):
    with patch(
        "notifications.contact_relay.requests.Session"
    ) as factory:

        mock_session(factory, status=status)

        with pytest.raises(RuntimeError):
            resolve_contact_via_relay("123@lid")


def test_invalid_token(relay_settings):
    relay_settings.OPENWA_PROXY_TOKEN = ""

    with patch(
        "notifications.contact_relay.requests.Session"
    ) as factory:

        with pytest.raises(ValueError):
            resolve_contact_via_relay("123@lid")

        factory.assert_not_called()



def test_explicit_recipient_rejection(relay_settings):
    from notifications.contact_relay import ContactNotAuthorized

    with patch(
        "notifications.contact_relay.requests.Session"
    ) as factory:
        mock_session(
            factory,
            status=403,
            body=b'{"error":"Recipient not authorized."}',
        )

        with pytest.raises(ContactNotAuthorized):
            resolve_contact_via_relay("123@lid")
