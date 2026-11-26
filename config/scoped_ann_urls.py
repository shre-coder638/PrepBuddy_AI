"""Expose only scoped ANN inference."""

from django.urls import path
from chatbot.ann.remote_service import ann_inference_scoped

urlpatterns = [
    path(
        "internal/ann/v2/answer/",
        ann_inference_scoped,
        name="scoped-ann-inference",
    ),
]
