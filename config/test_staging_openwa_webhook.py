"""Verify the restricted staging webhook exception."""

import hashlib
import hmac

import pytest
from django.test import Client


URL = "/api/notifications/openwa/webhook/"
SECRET = "w" * 64
BODY = b'{"event":"synthetic.ignored","data":{}}'


@pytest.fixture
def webhook_client(settings):
    settings.STAGING_MODE = True
    settings.STAGING_OPENWA_WEBHOOK_ENABLED = True
    settings.WHATSAPP_SEND_ENABLED = True
    settings.OPENWA_WEBHOOK_SECRET = SECRET
    settings.STAGING_ACCESS_TOKEN = "b" * 64
    settings.ALLOWED_HOSTS = ["testserver"]

    settings.MIDDLEWARE = [
        "config.staging.StagingAccessMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
    ]

    return Client(enforce_csrf_checks=True)


def post_webhook(client, valid=True):
    signature = "sha256=" + hmac.new(
        SECRET.encode(),
        BODY,
        hashlib.sha256,
    ).hexdigest()

    return client.post(
        URL,
        data=BODY,
        content_type="application/json",
        HTTP_X_OPENWA_SIGNATURE=(
            signature if valid else "invalid"
        ),
        secure=True,
    )


def test_signed_webhook_allowed(webhook_client):
    response = post_webhook(webhook_client)

    assert response.status_code == 200
    assert response.json()["ignored"] is True
    assert response["Cache-Control"] == "no-store"


def test_invalid_signature_rejected(webhook_client):
    assert post_webhook(
        webhook_client,
        valid=False,
    ).status_code == 401


@pytest.mark.parametrize("flag", [
    "STAGING_OPENWA_WEBHOOK_ENABLED",
    "WHATSAPP_SEND_ENABLED",
])
def test_disabled_webhook_blocked(
    webhook_client,
    settings,
    flag,
):
    setattr(settings, flag, False)

    response = post_webhook(webhook_client)

    assert response.status_code == 401
    assert "WWW-Authenticate" in response


@pytest.mark.parametrize("path", [
    "/admin/",
    "/api/patients/",
    URL + "extra/",
    URL,
])
def test_webhook_exception_is_not_general_access(
    webhook_client,
    path,
):
    assert webhook_client.get(
        path,
        secure=True,
    ).status_code == 401



def signed_inbound(client):
    body = (
        b'{"event":"message.received","data":'
        b'{"id":"synthetic-inbound-001",'
        b'"from":"123456789@lid","body":"DONE"}}'
    )

    signature = "sha256=" + hmac.new(
        SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    return client.post(
        URL,
        data=body,
        content_type="application/json",
        HTTP_X_OPENWA_SIGNATURE=signature,
        secure=True,
    )


@pytest.mark.django_db
def test_rejected_contact_is_not_retried(
    webhook_client,
    settings,
):
    from unittest.mock import patch

    from notifications.contact_relay import ContactNotAuthorized
    from notifications.models import ProcessedWhatsAppMessage

    settings.STAGING_WHATSAPP_DEMO_ENABLED = True
    settings.DEMO_ALLOWED_PHONE = "15550100101"
    settings.OPENWA_CONTACT_RELAY_URL = (
        "https://example.test"
        "/api/notifications/openwa/relay/resolve-contact/"
    )

    with patch(
        "notifications.contact_relay.resolve_contact_via_relay",
        side_effect=ContactNotAuthorized("Rejected"),
    ) as resolve, patch(
        "notifications.views.send_openwa_message",
    ) as send:

        response = signed_inbound(webhook_client)

        assert response.status_code == 200
        assert response.json()["authorized"] is False

        record = ProcessedWhatsAppMessage.objects.get(
            message_id="synthetic-inbound-001",
        )

        assert record.is_processed is True

        duplicate = signed_inbound(webhook_client)

        assert duplicate.status_code == 200
        assert duplicate.json()["duplicate"] is True

        resolve.assert_called_once()
        send.assert_not_called()


@pytest.mark.django_db
def test_contact_lookup_failure_remains_retryable(
    webhook_client,
    settings,
):
    from unittest.mock import patch

    from notifications.contact_relay import ContactNotAuthorized
    from notifications.models import ProcessedWhatsAppMessage

    settings.STAGING_WHATSAPP_DEMO_ENABLED = True
    settings.DEMO_ALLOWED_PHONE = "15550100101"
    settings.OPENWA_CONTACT_RELAY_URL = (
        "https://example.test"
        "/api/notifications/openwa/relay/resolve-contact/"
    )

    with patch(
        "notifications.contact_relay.resolve_contact_via_relay",
        side_effect=[
            RuntimeError("Synthetic network failure"),
            ContactNotAuthorized("Rejected"),
        ],
    ) as resolve, patch(
        "notifications.views.send_openwa_message",
    ) as send:

        response = signed_inbound(webhook_client)

        assert response.status_code == 502

        record = ProcessedWhatsAppMessage.objects.get(
            message_id="synthetic-inbound-001",
        )

        assert record.is_processed is False

        response = signed_inbound(webhook_client)

        assert response.status_code == 200
        assert response.json()["authorized"] is False

        record.refresh_from_db()

        assert record.is_processed is True
        assert resolve.call_count == 2

        send.assert_not_called()
