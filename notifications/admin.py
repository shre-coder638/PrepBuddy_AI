from django.contrib import admin
from .models import WhatsAppMessageAnalysis


@admin.register(WhatsAppMessageAnalysis)
class WhatsAppMessageAnalysisAdmin(admin.ModelAdmin):
    list_display = ("message", "sentiment", "emotion", "intent", "requires_human", "analyzed_at")
    list_filter = ("sentiment", "emotion", "intent", "requires_human")
    search_fields = ("message__content", "message__session__patient__phone_number")
    readonly_fields = ("message", "sentiment", "emotion", "intent", "confidence", "requires_human", "model_version", "analyzed_at")
