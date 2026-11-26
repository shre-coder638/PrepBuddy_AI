"""Recipient authorization for staging WhatsApp operations."""

import re

from django.conf import settings


def authorize_demo_chat(chat_id):
    if not getattr(settings, "STAGING_MODE", False):
        return

    if not getattr(
        settings, "STAGING_WHATSAPP_DEMO_ENABLED", False
    ):
        raise PermissionError("Staging delivery disabled.")

    allowed = getattr(settings, "DEMO_ALLOWED_PHONE", "")

    if not re.fullmatch(r"[1-9][0-9]{7,14}", allowed):
        raise PermissionError("Invalid demonstration recipient.")

    if not isinstance(chat_id, str) or not re.fullmatch(
        r"[0-9]{1,32}@(lid|c\.us|s\.whatsapp\.net)",
        chat_id,
    ):
        raise PermissionError("Invalid demonstration chat.")

    if chat_id.endswith("@c.us"):
        if chat_id != allowed + "@c.us":
            raise PermissionError("Recipient not authorized.")
        return

    from .contact_relay import resolve_contact_via_relay

    result = resolve_contact_via_relay(chat_id)

    if result["phone"] != allowed:
        raise PermissionError("Recipient not authorized.")
