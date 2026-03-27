"""Model translation registration for news models."""

from modeltranslation.translator import TranslationOptions, register

from news.models import Article, NewsTag


@register(Article)
class ArticleTranslationOptions(TranslationOptions):
    fields = ("title", "description", "content")


@register(NewsTag)
class NewsTagTranslationOptions(TranslationOptions):
    fields = ("title", "description")
