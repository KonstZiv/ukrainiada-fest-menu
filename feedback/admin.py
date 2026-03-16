from django.contrib import admin

from .models import GuestFeedback


@admin.register(GuestFeedback)
class GuestFeedbackAdmin(admin.ModelAdmin):
    list_display = [
        "visitor_name",
        "mood",
        "order",
        "is_published",
        "is_featured",
        "created_at",
    ]
    list_filter = ["mood", "is_published", "is_featured", "language"]
    list_editable = ["is_published", "is_featured"]
    search_fields = ["visitor_name", "message"]
    readonly_fields = [
        "order",
        "mood",
        "message",
        "visitor_name",
        "created_at",
        "language",
    ]
    ordering = ["-created_at"]
