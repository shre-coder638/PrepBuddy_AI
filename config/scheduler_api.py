"""Authenticated HTTPS scheduling for hybrid staging."""

import logging
import re
import secrets

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


logger = logging.getLogger(__name__)

SCHEDULER_PATH = "/internal/scheduler/v1/tick/"


def scheduler_response(payload, status=200):
    return JsonResponse(
        payload,
        status=status,
        headers={"Cache-Control": "no-store"},
    )


def scheduler_authenticated(request):
    if not (
        getattr(settings, "STAGING_MODE", False)
        and getattr(settings, "HTTPS_SCHEDULER_ENABLED", False)
    ):
        return False

    expected = getattr(settings, "HTTPS_SCHEDULER_TOKEN", "")

    if not isinstance(expected, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{32,128}",
        expected,
    ):
        return False

    if expected in (
        getattr(settings, "STAGING_ACCESS_TOKEN", ""),
        getattr(settings, "ANN_SERVICE_TOKEN", ""),
    ):
        return False

    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer":
        return False

    return secrets.compare_digest(
        token.encode("utf-8"),
        expected.encode("utf-8"),
    )


@csrf_exempt
def scheduler_tick(request):
    request.get_host()

    if not scheduler_authenticated(request):
        return scheduler_response(
            {"error": "Unauthorized"},
            status=401,
        )

    if request.method != "POST":
        result = scheduler_response(
            {"error": "Method not allowed"},
            status=405,
        )

        result["Allow"] = "POST"
        return result

    if request.content_type != "application/json":
        return scheduler_response(
            {"error": "Unsupported content type"},
            status=415,
        )

    # The heartbeat accepts exactly an empty JSON object.
    # No arbitrary task names or execution arguments.
    if (
        request.META.get("CONTENT_LENGTH") != "2"
        or request.META.get("QUERY_STRING")
        or request.body != b"{}"
    ):
        return scheduler_response(
            {"error": "Invalid scheduler request"},
            status=400,
        )

    try:
        from notifications.tasks import scheduler_heartbeat

        # Execute directly, without publishing a Celery task.
        result = scheduler_heartbeat.run()

        if (
            not isinstance(result, dict)
            or result.get("success") is not True
        ):
            raise RuntimeError("Heartbeat failed.")

        if getattr(
            settings,
            "HTTPS_SCHEDULER_DELIVERY_ENABLED",
            False,
        ):
            from .scheduler_execution import run_delivery_tick

            return scheduler_response(run_delivery_tick())

        if getattr(
            settings,
            "HTTPS_SCHEDULER_RECONCILE_ENABLED",
            False,
        ):
            from .scheduler_execution import (
                run_reconciliation_tick,
            )

            return scheduler_response(
                run_reconciliation_tick()
            )

        return scheduler_response({
            "status": "ok",
            "mode": "heartbeat-only",
        })

    except Exception as exc:
        logger.warning(
            "HTTPS scheduler tick failed: %s",
            type(exc).__name__,
        )

        return scheduler_response(
            {"error": "Scheduler unavailable"},
            status=503,
        )
