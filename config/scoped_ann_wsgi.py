"""Database-independent ANN WSGI application."""

import os

from django.core.wsgi import get_wsgi_application

os.environ["DJANGO_SETTINGS_MODULE"] = (
    "config.scoped_ann_settings"
)

application = get_wsgi_application()
