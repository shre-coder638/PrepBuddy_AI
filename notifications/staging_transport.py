"""Restricted outbound HTTPS transport for staging."""

import json
import re
from urllib.parse import urlsplit

import requests


SEND_PATH = "/api/notifications/openwa/relay/send-text/"
MAX_RESPONSE_BYTES = 16384


class RelayReply:
    def __init__(self, status_code, body=b""):
        self.status_code = status_code
        self.body = body

    def json(self):
        return json.loads(self.body)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"Relay returned HTTP {self.status_code}."
            )


def post_staging_relay(url, headers, payload):
    try:
        parsed = urlsplit(url)

        valid = (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
            and parsed.path == SEND_PATH
            and not parsed.query
            and not parsed.fragment
            and not any(c.isspace() for c in url)
        )

    except ValueError:
        valid = False

    if not valid:
        raise requests.RequestException(
            "Invalid staging relay URL."
        )

    if not re.fullmatch(
        r"[A-Za-z0-9_-]{32,128}",
        headers.get("X-Proxy-Token", ""),
    ):
        raise requests.RequestException(
            "Invalid staging relay credentials."
        )

    with requests.Session() as session:
        session.trust_env = False

        with session.post(
            url,
            headers=headers,
            json=payload,
            timeout=(5, 25),
            verify=True,
            allow_redirects=False,
            stream=True,
        ) as response:

            status = response.status_code

            if status >= 400:
                return RelayReply(status)

            if status != 200:
                raise requests.RequestException(
                    "Unexpected relay response status."
                )

            body = bytearray()

            for chunk in response.iter_content(1024):
                body.extend(chunk)

                if len(body) > MAX_RESPONSE_BYTES:
                    raise requests.RequestException(
                        "Relay response too large."
                    )

    try:
        result = json.loads(body)

        if (
            not isinstance(result, dict)
            or result.get("success") is not True
            or result.get("sent") is False
            or not isinstance(result.get("messageId"), str)
            or not result["messageId"].strip()
            or len(result["messageId"]) > 255
        ):
            raise ValueError("Invalid acceptance response.")

    except (ValueError, UnicodeError):
        raise requests.RequestException(
            "Uncertain relay acceptance."
        ) from None

    return RelayReply(200, bytes(body))
