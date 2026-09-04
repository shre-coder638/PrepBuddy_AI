from django.urls import path

from .views import confirm_reminder


urlpatterns = [
    path(
        "<str:token>/confirm/",
        confirm_reminder,
        name="confirm-reminder",
    ),
]