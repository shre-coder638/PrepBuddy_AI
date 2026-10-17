"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from patients.api_views import patients_list
from procedures.api_views import (
    procedures_list,
    procedure_timeline,
)
from .views import privacy_policy
from accounts.api_views import doctor_profile_api
from accounts.api_views import user_settings_api

urlpatterns = [
    path("admin/", admin.site.urls),

    path("", include("frontend.urls")),
    path("privacy-policy/", privacy_policy, name="privacy-policy"),

    path("api/reminders/", include("reminders.urls")),
    path("api/notifications/", include("notifications.urls")),
    path("api/protocols/", include("protocols.api_urls")),
    path("api/procedures/", procedures_list, name="procedures-list"),
    path(
        "api/procedures/<int:procedure_id>/timeline/",
        procedure_timeline,
        name="procedure-timeline-api",
    ),
    path(
        "api/patients/",
        patients_list,
        name="patients-list",
    ),
    path("api/doctor-profile/", doctor_profile_api, name="doctor-profile-api"),
    path("api/settings/", user_settings_api, name="user-settings-api"),
    path("api/chatbot/", include("chatbot.urls")),
]