"""Isolated settings for the local ANN inference service."""

import os

from django.core.exceptions import ImproperlyConfigured

from .settings import *


if not STAGING_MODE:
    raise ImproperlyConfigured(
        "The isolated ANN service requires staging mode."
    )

if CHATBOT_BACKEND != "ann":
    raise ImproperlyConfigured(
        "The local inference service requires the ANN backend."
    )

ANN_SERVICE_TOKEN = os.getenv(
    "ANN_SERVICE_TOKEN",
    "",
)

if len(ANN_SERVICE_TOKEN) < 32:
    raise ImproperlyConfigured(
        "The ANN service requires a strong service token."
    )

if ANN_SERVICE_TOKEN == STAGING_ACCESS_TOKEN:
    raise ImproperlyConfigured(
        "ANN and staging access tokens must be different."
    )

ROOT_URLCONF = "config.ann_service_urls"
WSGI_APPLICATION = "config.ann_service_wsgi.application"

# This service has no browser sessions or application routes.
# Authentication is performed by its dedicated inference view.
MIDDLEWARE = []

DATA_UPLOAD_MAX_MEMORY_SIZE = 16384

ANN_RECORD_EXPERIENCES = False
WHATSAPP_SEND_ENABLED = False
EMAIL_SEND_ENABLED = False
EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
