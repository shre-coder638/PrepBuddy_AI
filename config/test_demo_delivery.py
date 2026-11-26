"""Demonstration configuration and recipient safety tests."""

from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.demo_delivery import validate_demo_delivery
from notifications.demo_safety import authorize_demo_chat


BASE = "https://example.test"
PHONE = "15550100101"


@pytest.fixture
def demo_config():
    return {
        "staging": True,
        "backend": "remote_ann",
        "phone": PHONE,
        "ann_url": BASE + "/internal/ann/v2/answer/",
        "send_url": (
            BASE + "/api/notifications/openwa/relay/send-text/"
        ),
        "contact_url": (
            BASE + "/api/notifications/openwa/relay/resolve-contact/"
        ),
        "tokens": tuple(c * 64 for c in "abcde"),
    }


def test_valid_demo_configuration(demo_config):
    validate_demo_delivery(**demo_config)


@pytest.mark.parametrize("key,value", [
    ("staging", False),
    ("backend", "rag"),
    ("phone", ""),
    ("phone", "STAGING-NO-SEND-01"),
    ("ann_url", BASE + "/internal/ann/v1/answer/"),
    ("send_url", "http://localhost/"),
    ("contact_url",
     "https://different.test/api/notifications/openwa/relay/resolve-contact/"),
    ("tokens", ("a" * 64,) * 5),
    ("tokens", ("",) * 5),
])
def test_invalid_configuration(demo_config, key, value):
    demo_config[key] = value

    with pytest.raises(ImproperlyConfigured):
        validate_demo_delivery(**demo_config)


@pytest.fixture
def demo_settings(settings):
    settings.STAGING_MODE = True
    settings.STAGING_WHATSAPP_DEMO_ENABLED = True
    settings.DEMO_ALLOWED_PHONE = PHONE
    settings.WHATSAPP_SEND_ENABLED = True
    return settings


def test_allowed_phone(demo_settings):
    authorize_demo_chat(PHONE + "@c.us")


@pytest.mark.parametrize("chat", [
    "15550100102@c.us",
    "123@g.us",
    "../contacts",
    "",
])
def test_disallowed_chat(demo_settings, chat):
    with pytest.raises(PermissionError):
        authorize_demo_chat(chat)


def test_disabled_demo(demo_settings):
    demo_settings.STAGING_WHATSAPP_DEMO_ENABLED = False

    with pytest.raises(PermissionError):
        authorize_demo_chat(PHONE + "@c.us")


@pytest.mark.parametrize("phone,allowed", [
    (PHONE, True),
    ("15550100102", False),
])
def test_lid_authorization(demo_settings, phone, allowed):
    with patch(
        "notifications.contact_relay.resolve_contact_via_relay",
        return_value={"phone": phone},
    ):
        if allowed:
            authorize_demo_chat("123@lid")
        else:
            with pytest.raises(PermissionError):
                authorize_demo_chat("123@lid")


def test_unauthorized_send_creates_no_ledger(demo_settings):
    from notifications.whatsapp import send_openwa_message

    with patch(
        "notifications.whatsapp._get_or_create_outbound"
    ) as ledger:
        with pytest.raises(PermissionError):
            send_openwa_message(
                chat_id="15550100102@c.us",
                text="Synthetic test",
                dedupe_key="synthetic:1",
                purpose="test",
            )

        ledger.assert_not_called()


def test_local_mode_unchanged(demo_settings):
    demo_settings.STAGING_MODE = False

    authorize_demo_chat("123@c.us")
