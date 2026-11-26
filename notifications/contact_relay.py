"""Restricted HTTPS contact resolution for hybrid OpenWA."""

import json
import re
from urllib.parse import urlsplit

import requests
from django.conf import settings


CONTACT_PATH = "/api/notifications/openwa/relay/resolve-contact/"
MAX_RESPONSE_BYTES = 4096


class ContactNotAuthorized(PermissionError):
    """The gateway rejected a non-allowlisted contact."""


def resolve_contact_via_relay(sender):
    url = settings.OPENWA_CONTACT_RELAY_URL
    token = settings.OPENWA_PROXY_TOKEN

    parsed = urlsplit(url)

    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or parsed.path != CONTACT_PATH
        or parsed.query
        or parsed.fragment
        or any(char.isspace() for char in url)
    ):
        raise ValueError("Invalid contact relay URL.")

    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token):
        raise ValueError("Invalid contact relay token.")

    if not isinstance(sender, str) or not re.fullmatch(
        r"[0-9]{1,32}@(lid|c\.us|s\.whatsapp\.net)",
        sender,
    ):
        raise ValueError("Invalid WhatsApp sender.")

    with requests.Session() as session:
        session.trust_env = False

        with session.post(
            url,
            json={"chatId": sender},
            headers={"X-Proxy-Token": token},
            timeout=(5, 15),
            verify=True,
            allow_redirects=False,
            stream=True,
        ) as response:

            if response.status_code not in (200, 403):
                raise RuntimeError(
                    "Contact relay unavailable."
                )

            body = bytearray()

            for chunk in response.iter_content(chunk_size=1024):
                body.extend(chunk)

                if len(body) > MAX_RESPONSE_BYTES:
                    raise ValueError(
                        "Contact response too large."
                    )

            result = json.loads(body)

            if response.status_code == 403:
                if result == {
                    "error": "Recipient not authorized."
                }:
                    raise ContactNotAuthorized(
                        "Contact not authorized."
                    )

                raise RuntimeError(
                    "Contact relay unavailable."
                )

    if not isinstance(result, dict) or set(result) != {"phone"}:
        raise ValueError("Invalid contact response.")

    phone = result["phone"]

    if not isinstance(phone, str) or not re.fullmatch(
        r"\+?[1-9][0-9]{7,14}",
        phone,
    ):
        raise ValueError("Invalid contact phone number.")

    return {"phone": phone.lstrip("+")}
