"""Fail-closed configuration for staging WhatsApp delivery."""

import re
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured


PHONE_PATTERN = r"[1-9][0-9]{7,14}"
TOKEN_PATTERN = r"[A-Za-z0-9_-]{32,128}"


def validate_demo_delivery(
    *, staging, backend, phone, ann_url, send_url,
    contact_url, tokens,
):
    if not staging or backend != "remote_ann":
        raise ImproperlyConfigured(
            "Demo delivery requires staging and remote ANN."
        )

    if not re.fullmatch(PHONE_PATTERN, phone):
        raise ImproperlyConfigured(
            "Invalid demonstration phone number."
        )

    endpoints = (
        (ann_url, "/internal/ann/v2/answer/"),
        (
            send_url,
            "/api/notifications/openwa/relay/send-text/",
        ),
        (
            contact_url,
            "/api/notifications/openwa/relay/resolve-contact/",
        ),
    )

    hosts = set()

    for url, path in endpoints:
        try:
            parsed = urlsplit(url)

            valid = (
                parsed.scheme == "https"
                and bool(parsed.hostname)
                and parsed.username is None
                and parsed.password is None
                and parsed.port in (None, 443)
                and parsed.path == path
                and not parsed.query
                and not parsed.fragment
                and not any(c.isspace() for c in url)
            )
        except ValueError:
            valid = False

        if not valid:
            raise ImproperlyConfigured(
                "Invalid demonstration relay endpoint."
            )

        hosts.add(parsed.hostname)

    if len(hosts) != 1:
        raise ImproperlyConfigured(
            "Demo services must use the same gateway host."
        )

    if not all(
        isinstance(token, str)
        and re.fullmatch(TOKEN_PATTERN, token)
        for token in tokens
    ):
        raise ImproperlyConfigured(
            "Invalid demonstration credentials."
        )

    if len(set(tokens)) != len(tokens):
        raise ImproperlyConfigured(
            "Demonstration credentials must be independent."
        )
