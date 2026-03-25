"""Model translation registration for news models."""

from modeltranslation.translator import TranslationOptions, register

from news.models import Article, NewsTag, Topic


@register(Article)
class ArticleTranslationOptions(TranslationOptions):
    fields = ("title", "description", "content")


@register(Topic)
class TopicTranslationOptions(TranslationOptions):
    fields = ("title",)


@register(NewsTag)
class NewsTagTranslationOptions(TranslationOptions):
    fields = ("title",)
