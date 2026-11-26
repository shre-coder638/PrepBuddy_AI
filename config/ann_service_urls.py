"""URL configuration dedicated to local ANN inference."""

from django.urls import path
from chatbot.ann.remote_service import ann_inference


urlpatterns = [
    path(
        "internal/ann/v1/answer/",
        ann_inference,
        name="ann-inference",
    ),
]
