"""HTTPS transport for the isolated ANN inference service."""

import json
import re
import time
from urllib.parse import urlsplit

import requests

from .remote_service import (
    MAX_BODY_BYTES,
    unique_object,
    validate_payload,
)


ENDPOINT_PATH = "/internal/ann/v1/answer/"

CONNECT_TIMEOUT = 3.05
READ_TIMEOUT = 25
RESPONSE_BUDGET_SECONDS = 30

MAX_RESPONSE_BYTES = 131072


class RemoteANNError(Exception):
    """Remote inference could not be completed safely."""


def validate_configuration(url, token):
    if not isinstance(url, str) or not url:
        raise RemoteANNError("Missing inference endpoint.")

    try:
        parsed = urlsplit(url)

        valid = (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
            and parsed.path == ENDPOINT_PATH
            and not parsed.query
            and not parsed.fragment
            and not any(char.isspace() for char in url)
        )

    except ValueError:
        valid = False

    if not valid:
        raise RemoteANNError("Invalid inference endpoint.")

    if (
        not isinstance(token, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token)
    ):
        raise RemoteANNError("Invalid inference credential.")


def reject_constant(value):
    raise ValueError("Invalid JSON constant.")


def request_remote_ann(
    url,
    token,
    question,
    protocol_id=None,
    communication_style="neutral",
    requires_human=False,
):
    validate_configuration(url, token)

    try:
        payload = validate_payload({
            "question": question,
            "protocol_id": protocol_id,
            "communication_style": communication_style,
            "requires_human": requires_human,
        })

        body = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

    except (ValueError, UnicodeError):
        raise RemoteANNError(
            "Invalid inference request."
        ) from None

    if len(body) > MAX_BODY_BYTES:
        raise RemoteANNError("Inference request too large.")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Cache-Control": "no-store",
    }

    started = time.monotonic()

    try:
        with requests.Session() as session:

            # Avoid implicit proxy and netrc credentials.
            session.trust_env = False

            with session.post(
                url,
                data=body,
                headers=headers,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                allow_redirects=False,
                verify=True,
                stream=True,
            ) as result:

                if result.status_code != 200:
                    raise RemoteANNError(
                        "Inference service unavailable."
                    )

                content_type = result.headers.get(
                    "Content-Type", ""
                ).split(";", 1)[0].strip().lower()

                if content_type != "application/json":
                    raise RemoteANNError(
                        "Invalid inference content type."
                    )

                response_body = bytearray()

                for chunk in result.iter_content(
                    chunk_size=8192
                ):
                    if (
                        time.monotonic() - started
                        > RESPONSE_BUDGET_SECONDS
                    ):
                        raise RemoteANNError(
                            "Inference response timed out."
                        )

                    response_body.extend(chunk)

                    if len(response_body) > MAX_RESPONSE_BYTES:
                        raise RemoteANNError(
                            "Inference response too large."
                        )

                if (
                    time.monotonic() - started
                    > RESPONSE_BUDGET_SECONDS
                ):
                    raise RemoteANNError(
                        "Inference response timed out."
                    )

                payload = json.loads(
                    response_body.decode("utf-8"),
                    object_pairs_hook=unique_object,
                    parse_constant=reject_constant,
                )

                if not isinstance(payload, dict):
                    raise RemoteANNError(
                        "Invalid inference response."
                    )

                return payload

    except (
        requests.RequestException,
        ValueError,
        UnicodeError,
        RecursionError,
    ):
        raise RemoteANNError(
            "Remote inference failed."
        ) from None
