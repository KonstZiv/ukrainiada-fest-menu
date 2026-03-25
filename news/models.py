"""News app models — articles, topics, tags, images."""

from __future__ import annotations

import uuid
from functools import partial
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


def _upload_image(instance: object, filename: str, folder: str = "images") -> Path:
    stem = slugify(Path(filename).stem) + str(uuid.uuid4()) + Path(filename).suffix
    return Path(folder) / stem


upload_to_article_main = partial(_upload_image, folder="article_main_images")
upload_to_article_gallery = partial(_upload_image, folder="article_gallery_images")


class Topic(models.Model):
    """News rubric (e.g. Culture, Sport, Events)."""

    title = models.CharField(max_length=128)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title


class NewsTag(models.Model):
    """Fine-tuning tag for articles (e.g. ballet, children, cuisine)."""

    title = models.CharField(max_length=128)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title


class Article(models.Model):
    """News article with rich text content."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Чернетка")
        PUBLISHED = "published", _("Опублікована")
        ARCHIVED = "archived", _("Архівована")

    title = models.CharField(max_length=256, verbose_name=_("Заголовок"))
    description = models.CharField(
        max_length=512,
        verbose_name=_("Короткий опис"),
        help_text=_("Анонс для списку новин"),
    )
    content = models.TextField(
        verbose_name=_("Текст статті"),
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
        verbose_name=_("Рубрика"),
    )
    tags = models.ManyToManyField(
        NewsTag,
        blank=True,
        related_name="articles",
        verbose_name=_("Теги"),
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="articles",
        verbose_name=_("Автор"),
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
        verbose_name=_("Статус"),
    )
    is_urgent = models.BooleanField(
        default=False,
        verbose_name=_("Термінова"),
        help_text=_("Термінові новини надсилаються підписникам негайно"),
    )
    in_rotation = models.BooleanField(
        default=False,
        verbose_name=_("В ротації"),
        help_text=_("Показувати в каруселі на головній"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Стаття")
        verbose_name_plural = _("Статті")

    def __str__(self) -> str:
        return self.title


class ArticleMainImage(models.Model):
    """Required main image for an article."""

    title = models.CharField(max_length=128, verbose_name=_("Назва зображення"))
    image = models.ImageField(
        upload_to=upload_to_article_main,
        verbose_name=_("Головне зображення"),
    )
    article = models.OneToOneField(
        Article,
        on_delete=models.CASCADE,
        related_name="main_image",
    )

    def __str__(self) -> str:
        return self.title


class ArticleImage(models.Model):
    """Optional additional image for an article."""

    title = models.CharField(max_length=128, verbose_name=_("Назва зображення"))
    image = models.ImageField(
        upload_to=upload_to_article_gallery,
        verbose_name=_("Додаткове зображення"),
    )
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="images",
    )

    def __str__(self) -> str:
        return self.title


class TranslationFeedback(models.Model):
    """User-submitted feedback about translation inaccuracies."""

    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="translation_feedbacks",
    )
    language = models.CharField(max_length=10, verbose_name=_("Мова"))
    message = models.TextField(verbose_name=_("Повідомлення"))
    page_url = models.URLField(verbose_name=_("Сторінка"))
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Зауваження до перекладу")
        verbose_name_plural = _("Зауваження до перекладів")

    def __str__(self) -> str:
        return f"Feedback #{self.pk} [{self.language}] {self.article}"


class ArticleComment(models.Model):
    """User comment on an article (pre-moderated)."""

    class Status(models.TextChoices):
        PENDING = "pending", _("На розгляді")
        APPROVED = "approved", _("Схвалений")
        REJECTED = "rejected", _("Відхилений")

    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="article_comments",
    )
    message = models.TextField(
        max_length=2000,
        verbose_name=_("Коментар"),
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Коментар до статті")
        verbose_name_plural = _("Коментарі до статей")

    def __str__(self) -> str:
        return f"Comment #{self.pk} by {self.author} on {self.article}"


class DigestSubscription(models.Model):
    """User subscription to news digests."""

    class Frequency(models.TextChoices):
        DAILY = "daily", _("Щоденно")
        WEEKLY = "weekly", _("Щотижня")
        URGENT = "urgent", _("Тільки термінові")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="digest_subscription",
    )
    frequency = models.CharField(
        max_length=10,
        choices=Frequency.choices,
        default=Frequency.WEEKLY,
        verbose_name=_("Частота"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Активна"))
    last_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Підписка на дайджест")
        verbose_name_plural = _("Підписки на дайджести")

    def __str__(self) -> str:
        return f"{self.user} [{self.frequency}]"
