"""Restricted machine-to-machine ANN inference endpoint."""

import json
import logging
import secrets

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.http import JsonResponse


logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 16384
MAX_QUESTION_CHARS = 2000

ALLOWED_FIELDS = {
    "question",
    "protocol_id",
    "communication_style",
    "requires_human",
}


def response(payload, status=200):
    return JsonResponse(
        payload,
        status=status,
        headers={"Cache-Control": "no-store"},
    )


def authenticated(request):
    expected = getattr(settings, "ANN_SERVICE_TOKEN", "")

    if not isinstance(expected, str) or len(expected) < 32:
        return False

    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        return False

    return secrets.compare_digest(
        token.encode("utf-8"),
        expected.encode("utf-8"),
    )


def unique_object(pairs):
    result = {}

    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")

        result[key] = value

    return result


def validate_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("Invalid request object")

    if set(payload) - ALLOWED_FIELDS:
        raise ValueError("Unknown request field")

    question = payload.get("question")

    if (
        not isinstance(question, str)
        or not question.strip()
        or len(question) > MAX_QUESTION_CHARS
    ):
        raise ValueError("Invalid question")

    protocol_id = payload.get("protocol_id")

    if protocol_id is not None and (
        type(protocol_id) is not int
        or not 0 < protocol_id <= 9223372036854775807
    ):
        raise ValueError("Invalid protocol ID")

    style = payload.get(
        "communication_style",
        "neutral",
    )

    if (
        not isinstance(style, str)
        or not style.strip()
        or len(style) > 64
    ):
        raise ValueError("Invalid communication style")

    requires_human = payload.get(
        "requires_human",
        False,
    )

    if type(requires_human) is not bool:
        raise ValueError("Invalid escalation flag")

    return {
        "question": question.strip(),
        "protocol_id": protocol_id,
        "communication_style": style.strip(),
        "requires_human": requires_human,
    }


def invoke_ann(**kwargs):
    # Import neural network dependencies only when required.
    from .backend import answer_configured_ann

    return answer_configured_ann(**kwargs)


def reject_constant(value):
    raise ValueError("Invalid JSON constant")


def handle_inference(
    request,
    *,
    max_body_bytes,
    validator,
    inference,
):
    request.get_host()

    if not authenticated(request):
        return response(
            {"error": "Unauthorized"},
            status=401,
        )

    if request.method != "POST":
        result = response(
            {"error": "Method not allowed"},
            status=405,
        )
        result["Allow"] = "POST"
        return result

    if request.content_type != "application/json":
        return response(
            {"error": "Unsupported content type"},
            status=415,
        )

    try:
        length = int(request.META.get("CONTENT_LENGTH", ""))

        if length <= 0:
            raise ValueError("Invalid content length")

    except (TypeError, ValueError):
        return response(
            {"error": "Invalid content length"},
            status=400,
        )

    if length > max_body_bytes:
        return response(
            {"error": "Request too large"},
            status=413,
        )

    try:
        body = request.body

        if len(body) != length:
            raise ValueError("Invalid body length")

        payload = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )

        arguments = validator(payload)

    except RequestDataTooBig:
        return response(
            {"error": "Request too large"},
            status=413,
        )

    except (ValueError, UnicodeError, RecursionError):
        return response(
            {"error": "Invalid inference request"},
            status=400,
        )

    try:
        result = inference(**arguments)

        if not isinstance(result, dict):
            raise ValueError("Invalid ANN response")

        return response(result)

    except Exception as exc:
        logger.error(
            "Remote ANN inference failure: %s",
            type(exc).__name__,
        )

        return response(
            {"error": "Inference unavailable"},
            status=503,
        )



def ann_inference(request):
    """Legacy database-backed inference endpoint."""

    return handle_inference(
        request,
        max_body_bytes=MAX_BODY_BYTES,
        validator=validate_payload,
        inference=invoke_ann,
    )


def ann_inference_scoped(request):
    """Database-independent scoped inference endpoint."""

    from .remote_protocol import (
        MAX_SCOPED_BODY_BYTES,
        validate_scoped_payload,
        invoke_scoped_ann,
    )

    return handle_inference(
        request,
        max_body_bytes=MAX_SCOPED_BODY_BYTES,
        validator=validate_scoped_payload,
        inference=invoke_scoped_ann,
    )
