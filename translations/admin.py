"""Admin registration for TranslationApproval."""

from django.contrib import admin

from translations.models import TranslationApproval


@admin.register(TranslationApproval)
class TranslationApprovalAdmin(admin.ModelAdmin[TranslationApproval]):
    list_display = [
        "content_type",
        "object_id",
        "language",
        "status",
        "approved_by",
        "created_at",
    ]
    list_filter = ["status", "language", "content_type"]
    readonly_fields = ["content_type", "object_id", "language", "created_at"]
