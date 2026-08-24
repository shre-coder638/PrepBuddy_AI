from django.contrib import admin
from .models import Procedure


@admin.register(Procedure)
class ProcedureAdmin(admin.ModelAdmin):
    list_display = (
        "procedure_name",
        "patient",
        "scheduled_at",
        "status",
    )

    list_filter = ("status", "protocol")
    search_fields = (
        "procedure_name",
        "patient__first_name",
        "patient__last_name",
    )