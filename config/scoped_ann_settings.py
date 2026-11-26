"""Independent settings for scoped ANN inference."""

import os
import re
import secrets

from pathlib import Path
from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = secrets.token_urlsafe(48)
DEBUG = False

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

ROOT_URLCONF = "config.scoped_ann_urls"
WSGI_APPLICATION = "config.scoped_ann_wsgi.application"

STAGING_MODE = True
STAGING_EXTERNAL_CONNECTIONS = False

CHATBOT_BACKEND = "ann"
ANN_RECORD_EXPERIENCES = False

ANN_SERVICE_TOKEN = os.getenv("ANN_SERVICE_TOKEN", "")

if not re.fullmatch(
    r"[A-Za-z0-9_-]{32,128}",
    ANN_SERVICE_TOKEN,
):
    raise ImproperlyConfigured(
        "A strong ANN service token is required."
    )

# Register application models without enabling database access.
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "django_celery_beat",
    "accounts",
    "clinics",
    "patients",
    "procedures",
    "protocols",
    "reminders",
    "notifications",
    "chatbot",
    "frontend",
]

MIDDLEWARE = []

# Any accidental ORM operation must fail.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.dummy",
    }
}

# No external task broker.
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = None

WHATSAPP_SEND_ENABLED = False
EMAIL_SEND_ENABLED = False
EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"

DATA_UPLOAD_MAX_MEMORY_SIZE = 131072

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
