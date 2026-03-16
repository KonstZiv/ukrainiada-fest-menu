"""Model translation registration for menu models."""

from modeltranslation.translator import TranslationOptions, register

from menu.models import Category, Dish, Tag


@register(Category)
class CategoryTranslationOptions(TranslationOptions):
    fields = ("title", "description")


@register(Dish)
class DishTranslationOptions(TranslationOptions):
    fields = ("title", "description")


@register(Tag)
class TagTranslationOptions(TranslationOptions):
    fields = ("title", "description")
