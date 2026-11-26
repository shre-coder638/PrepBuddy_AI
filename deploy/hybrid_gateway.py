"""Database-independent gateway for PrepBuddy staging."""

import hmac
import json
import re

from http import HTTPStatus
from urllib.parse import quote
from uuid import UUID

import requests


ANN_PATH = "/internal/ann/v2/answer/"
CONTACT_PATH = "/api/notifications/openwa/relay/resolve-contact/"
SEND_PATH = "/api/notifications/openwa/relay/send-text/"

ANN_BASE = "http://127.0.0.1:8011"
OPENWA_BASE = "http://127.0.0.1:2785"

ROUTES = {ANN_PATH, CONTACT_PATH, SEND_PATH}

CHAT_PATTERN = r"[0-9]{1,32}@(lid|c\.us|s\.whatsapp\.net)"
PHONE_PATTERN = r"[1-9][0-9]{7,14}"
TOKEN_PATTERN = r"[A-Za-z0-9_-]{32,128}"


class Reject(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message


def matches_token(received, expected):
    return hmac.compare_digest(
        received.encode("utf-8"),
        expected.encode("utf-8"),
    )


def unique_object(pairs):
    result = {}

    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field.")

        result[key] = value

    return result


def invalid_constant(value):
    raise ValueError("Invalid JSON constant.")


def decode_json(body):
    return json.loads(
        body,
        object_pairs_hook=unique_object,
        parse_constant=invalid_constant,
    )


def upstream(method, url, headers, body=None,
             limit=4096, timeout=(2, 10)):
    """Call a fixed local upstream without forwarding credentials."""

    with requests.Session() as session:
        session.trust_env = False

        with session.request(
            method,
            url,
            headers=headers,
            data=body,
            timeout=timeout,
            allow_redirects=False,
            stream=True,
        ) as response:

            result = bytearray()

            for chunk in response.iter_content(1024):
                result.extend(chunk)

                if len(result) > limit:
                    raise RuntimeError("Upstream response too large.")

            return response.status_code, bytes(result)


def create_app(*, ann_token, proxy_token, openwa_key,
               session_id, allowed_phone, allow_send=False):

    if not all(
        isinstance(token, str)
        and re.fullmatch(TOKEN_PATTERN, token)
        for token in (ann_token, proxy_token)
    ):
        raise ValueError("Invalid gateway credentials.")

    if ann_token == proxy_token:
        raise ValueError("Gateway tokens must be independent.")

    if not openwa_key or not session_id:
        raise ValueError("OpenWA credentials are required.")

    if not re.fullmatch(PHONE_PATTERN, allowed_phone):
        raise ValueError("Invalid demonstration phone number.")

    session_path = (
        OPENWA_BASE + "/api/sessions/"
        + quote(session_id, safe="")
    )

    def validate_chat(chat):
        if not isinstance(chat, str) or not re.fullmatch(
            CHAT_PATTERN, chat
        ):
            raise Reject(400, "Invalid chat identifier.")

    def resolve_phone(chat):
        validate_chat(chat)

        status, body = upstream(
            "GET",
            session_path + "/contacts/"
            + quote(chat, safe="") + "/phone",
            {"X-API-Key": openwa_key},
            timeout=(2, 6),
        )

        if status != 200:
            raise Reject(502, "Contact lookup unavailable.")

        result = decode_json(body)

        if not isinstance(result, dict):
            raise Reject(502, "Invalid contact response.")

        phone = result.get("phone")

        if not isinstance(phone, str):
            raise Reject(502, "Invalid contact response.")

        phone = phone.removeprefix("+")

        if not re.fullmatch(PHONE_PATTERN, phone):
            raise Reject(502, "Invalid contact phone.")

        if phone != allowed_phone:
            raise Reject(403, "Recipient not authorized.")

        return phone

    def dispatch(env):
        path = env.get("PATH_INFO", "")

        if path not in ROUTES:
            raise Reject(404, "Not found.")

        if env.get("REQUEST_METHOD") != "POST":
            raise Reject(405, "POST required.")

        if env.get("QUERY_STRING"):
            raise Reject(400, "Query parameters not allowed.")

        if path == ANN_PATH:
            authorized = matches_token(
                env.get("HTTP_AUTHORIZATION", ""),
                "Bearer " + ann_token,
            )
        else:
            authorized = matches_token(
                env.get("HTTP_X_PROXY_TOKEN", ""),
                proxy_token,
            )

        if not authorized:
            raise Reject(401, "Unauthorized.")

        if path == SEND_PATH and allow_send is not True:
            raise Reject(503, "Gateway delivery disabled.")

        if env.get("CONTENT_TYPE", "").split(";")[0].strip() != (
            "application/json"
        ):
            raise Reject(415, "JSON required.")

        length = env.get("CONTENT_LENGTH", "")

        if not re.fullmatch(r"[0-9]{1,9}", length):
            raise Reject(400, "Invalid Content-Length.")

        length = int(length)
        limit = 131072 if path == ANN_PATH else 65536

        if length > limit:
            raise Reject(413, "Request too large.")

        body = env["wsgi.input"].read(length)

        if len(body) != length:
            raise Reject(400, "Incomplete request.")

        try:
            payload = decode_json(body)
        except (ValueError, UnicodeError, RecursionError):
            raise Reject(400, "Invalid JSON.") from None

        if not isinstance(payload, dict):
            raise Reject(400, "Invalid payload.")

        if path == ANN_PATH:
            status, result = upstream(
                "POST",
                ANN_BASE + ANN_PATH,
                {
                    "Authorization": "Bearer " + ann_token,
                    "Content-Type": "application/json",
                },
                body,
                limit=131072,
                timeout=(2, 25),
            )

            if status not in (
                200, 400, 401, 413, 415, 503
            ):
                raise Reject(502, "ANN unavailable.")

            return status, result

        expected = (
            {"chatId"}
            if path == CONTACT_PATH
            else {"chatId", "text"}
        )

        if set(payload) != expected:
            raise Reject(400, "Unexpected payload fields.")

        chat = payload["chatId"]
        validate_chat(chat)

        if path == CONTACT_PATH:
            return 200, json.dumps({
                "phone": resolve_phone(chat),
            }).encode()

        message = payload["text"]

        if (
            not isinstance(message, str)
            or not message.strip()
            or len(message) > 16000
        ):
            raise Reject(400, "Invalid message text.")

        try:
            key = str(UUID(
                env.get("HTTP_IDEMPOTENCY_KEY", "")
            ))
        except (ValueError, TypeError):
            raise Reject(
                400, "Valid idempotency key required."
            ) from None

        if chat.endswith("@c.us"):
            if chat.split("@")[0] != allowed_phone:
                raise Reject(403, "Recipient not authorized.")
        else:
            resolve_phone(chat)

        status, result = upstream(
            "POST",
            session_path + "/messages/send-text",
            {
                "X-API-Key": openwa_key,
                "Content-Type": "application/json",
                "Idempotency-Key": key,
            },
            body,
            timeout=(2, 8),
        )

        if status == 409:
            raise Reject(409, "Send outcome uncertain.")

        if not 200 <= status < 300:
            raise Reject(502, "OpenWA send unavailable.")

        data = decode_json(result)

        if (
            not isinstance(data, dict)
            or data.get("success") is False
            or data.get("sent") is False
            or not (
                data.get("success") is True
                or data.get("sent") is True
            )
            or not isinstance(data.get("messageId"), str)
            or not data["messageId"].strip()
        ):
            raise Reject(502, "Send acceptance uncertain.")

        return 200, json.dumps({
            "success": True,
            "messageId": data["messageId"],
        }).encode()

    def application(env, start_response):
        try:
            status, body = dispatch(env)

        except Reject as exc:
            status = exc.status
            body = json.dumps({
                "error": exc.message
            }).encode()

        except Exception:
            status = 502
            body = b'{"error":"Upstream unavailable"}'

        start_response(
            f"{status} {HTTPStatus(status).phrase}",
            [
                ("Content-Type", "application/json"),
                ("Cache-Control", "no-store"),
                ("Content-Length", str(len(body))),
            ],
        )

        return [body]

    return application
