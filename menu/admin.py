from django.contrib import admin
from modeltranslation.admin import TabbedTranslationAdmin

from .models import (
    Allergen,
    Category,
    CategoryLogo,
    Dish,
    DishMainImage,
    DishPicture,
    Tag,
    TagLogo,
)


class DishMainImageInline(admin.StackedInline):
    model = DishMainImage
    min_num = 1
    max_num = 1


class DishPictureInline(admin.TabularInline):
    model = DishPicture
    extra = 1


class CategoryLogoInline(admin.StackedInline):
    model = CategoryLogo
    max_num = 1


class TagLogoInline(admin.StackedInline):
    model = TagLogo
    max_num = 1


@admin.register(Category)
class CategoryAdmin(TabbedTranslationAdmin):
    list_display = ["title", "number_in_line"]
    list_editable = ["number_in_line"]
    ordering = ["number_in_line", "title"]
    inlines = [CategoryLogoInline]


@admin.register(Tag)
class TagAdmin(TabbedTranslationAdmin):
    list_display = ["title"]
    search_fields = ["title_uk", "title_en"]
    ordering = ["title"]
    inlines = [TagLogoInline]


@admin.register(Dish)
class DishAdmin(TabbedTranslationAdmin):
    list_display = ["title", "category", "price", "availability"]
    list_filter = ["availability", "category"]
    list_editable = ["availability"]
    search_fields = ["title_uk", "title_en"]
    ordering = ["category", "title"]
    inlines = [DishMainImageInline, DishPictureInline]


@admin.register(Allergen)
class AllergenAdmin(TabbedTranslationAdmin):
    list_display = ["title", "icon"]
    search_fields = ["title_uk", "title_en"]
    ordering = ["title"]
