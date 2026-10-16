from django.urls import path

from .views import protocol_list


urlpatterns = [
    path("", protocol_list, name="protocol-list"),
]
