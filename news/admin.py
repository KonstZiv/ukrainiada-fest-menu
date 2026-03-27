"""Admin registration for news models."""

from django.contrib import admin
from django.core.exceptions import ValidationError
from modeltranslation.admin import TabbedTranslationAdmin

from news.models import (
    Article,
    ArticleComment,
    ArticleImage,
    ArticleMainImage,
    DigestSubscription,
    NewsTag,
    NewsTagLogo,
)


class ArticleMainImageInline(admin.StackedInline[ArticleMainImage, Article]):
    model = ArticleMainImage
    min_num = 1
    max_num = 1


class ArticleImageInline(admin.TabularInline[ArticleImage, Article]):
    model = ArticleImage
    extra = 1


@admin.register(Article)
class ArticleAdmin(TabbedTranslationAdmin):
    list_display = [
        "title",
        "primary_tag",
        "author",
        "status",
        "is_urgent",
        "in_rotation",
        "created_at",
    ]
    list_filter = ["status", "primary_tag", "is_urgent", "in_rotation", "created_at"]
    list_editable = ["status", "is_urgent", "in_rotation"]
    search_fields = ["title_uk", "title_en"]
    ordering = ["-created_at"]
    inlines = [ArticleMainImageInline, ArticleImageInline]

    def save_related(
        self, request: object, form: object, formsets: object, change: bool
    ) -> None:  # type: ignore[override]
        super().save_related(request, form, formsets, change)  # type: ignore[arg-type]
        article = form.instance  # type: ignore[attr-defined]
        if (
            article.primary_tag
            and article.tags.filter(pk=article.primary_tag_id).exists()
        ):
            article.tags.remove(article.primary_tag)


class NewsTagLogoInline(admin.StackedInline[NewsTagLogo, NewsTag]):
    model = NewsTagLogo
    min_num = 0
    max_num = 1


@admin.register(NewsTag)
class NewsTagAdmin(TabbedTranslationAdmin):
    list_display = ["title"]
    search_fields = ["title_uk", "title_en"]
    inlines = [NewsTagLogoInline]


@admin.register(ArticleComment)
class ArticleCommentAdmin(admin.ModelAdmin[ArticleComment]):
    list_display = ["article", "author", "status", "created_at"]
    list_filter = ["status", "created_at"]
    list_editable = ["status"]
    search_fields = ["message", "author__email"]
    readonly_fields = ["article", "author", "message", "created_at"]


@admin.register(DigestSubscription)
class DigestSubscriptionAdmin(admin.ModelAdmin[DigestSubscription]):
    list_display = ["user", "frequency", "is_active", "last_sent_at"]
    list_filter = ["frequency", "is_active"]
