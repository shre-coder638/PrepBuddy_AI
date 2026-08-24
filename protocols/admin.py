from django.contrib import admin
from .models import PrepProtocol, PrepStep


class PrepStepInline(admin.TabularInline):
    model = PrepStep
    extra = 1


@admin.register(PrepProtocol)
class PrepProtocolAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    inlines = [PrepStepInline]


@admin.register(PrepStep)
class PrepStepAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "protocol",
        "minutes_before_procedure",
        "requires_confirmation",
        "is_critical",
    )