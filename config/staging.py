import base64
import binascii
import secrets

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_safe

from .scheduler_api import (
    SCHEDULER_PATH,
    scheduler_authenticated,
    scheduler_response,
)


@require_safe
def healthz(request):
    return JsonResponse(
        {"status": "ok"},
        headers={"Cache-Control": "no-store"},
    )


class StagingAccessMiddleware:
    """Require separate staging credentials for application access."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.path_info
                == "/api/notifications/openwa/webhook/"
            and request.method == "POST"
            and getattr(
                settings,
                "STAGING_OPENWA_WEBHOOK_ENABLED",
                False,
            )
            and getattr(
                settings,
                "WHATSAPP_SEND_ENABLED",
                False,
            )
        ):
            # The webhook independently verifies its HMAC
            # signature before processing any events.
            response = self.get_response(request)
            response["Cache-Control"] = "no-store"
            return response

        if request.path_info == SCHEDULER_PATH:
            if not scheduler_authenticated(request):
                return scheduler_response(
                    {"error": "Unauthorized"},
                    status=401,
                )

            response = self.get_response(request)
            response["Cache-Control"] = "no-store"
            return response

        if (
            request.path_info == "/healthz/"
            and request.method in ("GET", "HEAD")
        ):
            return self.get_response(request)

        authorization = request.headers.get("Authorization", "")
        scheme, _, encoded = authorization.partition(" ")

        authorized = False

        if scheme.lower() == "basic":
            try:
                decoded = base64.b64decode(encoded, validate=True)
                username, separator, password = decoded.partition(b":")

                expected = settings.STAGING_ACCESS_TOKEN.encode("utf-8")

                username_ok = secrets.compare_digest(
                    username, b"staging"
                )
                password_ok = secrets.compare_digest(
                    password, expected
                )

                authorized = bool(
                    separator
                    and expected
                    and username_ok
                    and password_ok
                )

            except (ValueError, binascii.Error):
                authorized = False

        if not authorized:
            return HttpResponse(
                "Staging authentication required.",
                status=401,
                headers={
                    "WWW-Authenticate": 'Basic realm="PrepBuddy Staging"',
                    "Cache-Control": "no-store",
                },
            )

        response = self.get_response(request)
        response["Cache-Control"] = "private, no-store"
        return response
