from django.urls import path

from .views import confirm_reminder, create_reminder_follow_up


urlpatterns = [
    path(
        "<str:token>/confirm/",
        confirm_reminder,
        name="confirm-reminder",
    ),
    path(
        "follow-ups/",
        create_reminder_follow_up,
        name="create-reminder-follow-up",
    ),
]
