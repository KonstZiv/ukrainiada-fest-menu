"""Admin registration for news models."""

from django.contrib import admin
from modeltranslation.admin import TabbedTranslationAdmin

from news.models import Article, ArticleImage, ArticleMainImage, NewsTag, Topic


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


@admin.register(Topic)
class TopicAdmin(TabbedTranslationAdmin):
    list_display = ["title"]
    search_fields = ["title_uk", "title_en"]


@admin.register(NewsTag)
class NewsTagAdmin(TabbedTranslationAdmin):
    list_display = ["title"]
    search_fields = ["title_uk", "title_en"]
