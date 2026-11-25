from django.urls import path
from . import views

urlpatterns = [
    path(
        "openwa/webhook/",
        views.openwa_webhook,
        name="openwa-webhook"
    ),
    path(
        "openwa/relay/send-text/",
        views.openwa_relay_send_text,
        name="openwa-relay-send-text",
    ),
]