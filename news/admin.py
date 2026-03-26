"""Admin registration for news models."""

from django.contrib import admin
from modeltranslation.admin import TabbedTranslationAdmin

from news.models import (
    Article,
    ArticleComment,
    ArticleImage,
    ArticleMainImage,
    DigestSubscription,
    NewsTag,
    NewsTagLogo,
    Topic,
    TopicLogo,
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
        "topic",
        "author",
        "status",
        "is_urgent",
        "in_rotation",
        "created_at",
    ]
    list_filter = ["status", "topic", "is_urgent", "in_rotation", "created_at"]
    list_editable = ["status", "is_urgent", "in_rotation"]
    search_fields = ["title_uk", "title_en"]
    ordering = ["-created_at"]
    inlines = [ArticleMainImageInline, ArticleImageInline]


class TopicLogoInline(admin.StackedInline[TopicLogo, Topic]):
    model = TopicLogo
    min_num = 0
    max_num = 1


@admin.register(Topic)
class TopicAdmin(TabbedTranslationAdmin):
    list_display = ["title"]
    search_fields = ["title_uk", "title_en"]
    inlines = [TopicLogoInline]


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
