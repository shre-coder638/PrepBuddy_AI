"""URL configuration dedicated to local ANN inference."""

from django.urls import path
from chatbot.ann.remote_service import (
    ann_inference,
    ann_inference_scoped,
)


urlpatterns = [
    path(
        "internal/ann/v2/answer/",
        ann_inference_scoped,
        name="ann-inference-scoped",
    ),
    path(
        "internal/ann/v1/answer/",
        ann_inference,
        name="ann-inference",
    ),
]
