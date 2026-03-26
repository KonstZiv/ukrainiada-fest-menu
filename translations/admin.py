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
        "llm_average",
        "llm_review_iterations",
        "approved_by",
        "created_at",
    ]
    list_filter = ["status", "language", "content_type"]
    readonly_fields = [
        "content_type",
        "object_id",
        "language",
        "created_at",
        "llm_accuracy",
        "llm_emotion",
        "llm_quality",
        "llm_style",
        "llm_grammar",
        "llm_ethics",
        "llm_average",
        "llm_review_comment",
        "llm_review_iterations",
    ]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "content_type",
                    "object_id",
                    "language",
                    "status",
                    "approved_by",
                    "approved_at",
                    "created_at",
                ]
            },
        ),
        (
            "LLM Review Scores",
            {
                "fields": [
                    "llm_accuracy",
                    "llm_emotion",
                    "llm_quality",
                    "llm_style",
                    "llm_grammar",
                    "llm_ethics",
                    "llm_average",
                    "llm_review_comment",
                    "llm_review_iterations",
                ],
                "classes": ["collapse"],
            },
        ),
    ]
