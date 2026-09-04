from django.contrib import admin
from .models import Reminder


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = (
        "procedure",
        "prep_step",
        "scheduled_at",
        "status",
        "sent_at",
        "confirmed_at",
    )

    list_filter = ("status",)
    search_fields = (
        "procedure__patient__first_name",
        "procedure__patient__last_name",
        "prep_step__title",
    )