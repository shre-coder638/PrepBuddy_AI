"""Dedicated WSGI entry point for ANN inference."""

import os

from django.core.wsgi import get_wsgi_application


os.environ["DJANGO_SETTINGS_MODULE"] = (
    "config.ann_service_settings"
)

application = get_wsgi_application()
