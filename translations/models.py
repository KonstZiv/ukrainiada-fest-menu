"""Translation approval tracking for menu content."""

from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _


class TranslationApproval(models.Model):
    """Track approval status of LLM-generated translations per object per language."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Очікує")
        APPROVED = "approved", _("Затверджено")
        FAILED = "failed", _("Помилка перекладу")

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="translation_approvals",
    )
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    language = models.CharField(max_length=10, db_index=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_translations",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # --- LLM reviewer scores (0.0 – 10.0) ---
    llm_accuracy = models.FloatField(
        null=True, blank=True, help_text="Meaning accuracy (0-10)"
    )
    llm_emotion = models.FloatField(
        null=True, blank=True, help_text="Emotion accuracy (0-10)"
    )
    llm_quality = models.FloatField(
        null=True, blank=True, help_text="Translation quality (0-10)"
    )
    llm_style = models.FloatField(
        null=True, blank=True, help_text="Stylistic quality (0-10)"
    )
    llm_grammar = models.FloatField(
        null=True, blank=True, help_text="Grammar correctness (0-10)"
    )
    llm_ethics = models.FloatField(
        null=True, blank=True, help_text="Ethical appropriateness (0-10)"
    )
    llm_average = models.FloatField(
        null=True, blank=True, help_text="Average of all scores"
    )
    llm_review_comment = models.TextField(
        blank=True, default="", help_text="Reviewer feedback / correction notes"
    )
    llm_review_iterations = models.PositiveSmallIntegerField(
        default=0, help_text="Number of translate-review cycles"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "language"],
                name="unique_translation_approval",
            ),
        ]
        indexes = [
            models.Index(fields=["status"]),
        ]
        verbose_name = _("Затвердження перекладу")
        verbose_name_plural = _("Затвердження перекладів")

    def __str__(self) -> str:
        return f"{self.content_type.model}#{self.object_id} [{self.language}] {self.status}"
