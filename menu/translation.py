"""Model translation registration for menu models."""

from modeltranslation.translator import TranslationOptions, register

from menu.models import Allergen, Category, Dish, Tag


@register(Category)
class CategoryTranslationOptions(TranslationOptions):
    fields = ("title", "description")


@register(Dish)
class DishTranslationOptions(TranslationOptions):
    fields = ("title", "description")


@register(Allergen)
class AllergenTranslationOptions(TranslationOptions):
    fields = ("title",)


@register(Tag)
class TagTranslationOptions(TranslationOptions):
    fields = ("title", "description")
