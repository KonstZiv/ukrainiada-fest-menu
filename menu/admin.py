from django.contrib import admin

from .models import (
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
class CategoryAdmin(admin.ModelAdmin):
    # list_display — які колонки показувати у списку об'єктів.
    # Документація:
    #   https://docs.djangoproject.com/en/stable/ref/contrib/admin/#django.contrib.admin.ModelAdmin.list_display
    list_display = ["title", "number_in_line"]
    # list_editable — колонки, які можна редагувати прямо у списку (без відкриття форми).
    # Поле НЕ може бути одночасно в list_display першим елементом і в list_editable.
    # Документація:
    #   https://docs.djangoproject.com/en/stable/ref/contrib/admin/#django.contrib.admin.ModelAdmin.list_editable
    list_editable = ["number_in_line"]
    inlines = [CategoryLogoInline]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    inlines = [TagLogoInline]


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "price", "availability"]
    list_filter = ["availability", "category"]
    list_editable = ["availability"]
    inlines = [DishMainImageInline, DishPictureInline]
