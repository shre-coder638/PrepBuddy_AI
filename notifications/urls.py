from django.urls import path
from . import views

urlpatterns = [
    path(
        "openwa/webhook/",
        views.openwa_webhook,
        name="openwa-webhook"
    ),
]