# ---------------------------------------------------------------------------
# urls.py — Маршрути (URL patterns) застосунку menu
#
# Кожен path() пов'язує URL-адресу з відповідною view-функцією.
# app_name задає namespace — дозволяє використовувати {% url "menu:index" %}
# замість просто {% url "index" %}, уникаючи конфліктів імен.
#
# Документація Django URL dispatcher:
#   https://docs.djangoproject.com/en/stable/topics/http/urls/
# ---------------------------------------------------------------------------

from django.urls import path

from .views import (
    CategoryDeleteView,
    DishCreateView,
    DishDeleteView,
    DishUpdateView,
    TagCreateView,
    TagDeleteView,
    TagListView,
    TagUpdateView,
    category_create,
    category_list,
    category_update,
    dish_detail,
    dish_list,
    dish_search,
    index,
)

app_name = "menu"

urlpatterns = [
    path("", index, name="index"),
    # --- Категорії --- #
    # Список категорій з accordion (таска 1.5)
    path("categories/", category_list, name="category_list"),
    # Створення категорії через FBV (таска 2.1)
    # ВАЖЛИВО: create/ ПЕРЕД <int:pk>/, щоб Django не сприйняв "create" як pk.
    # Документація URL ordering:
    #   https://docs.djangoproject.com/en/stable/topics/http/urls/#how-django-processes-a-request
    path("categories/create/", category_create, name="category_create"),
    # Редагування категорії через FBV (таска 2.7)
    # Аналогічно до tag update, але FBV замість CBV — порівняння підходів.
    path("categories/<int:pk>/edit/", category_update, name="category_update"),
    # Видалення категорії через generic DeleteView (таска 2.7)
    # НЕБЕЗПЕЧНА операція — каскадно видаляє всі страви та зображення.
    # GET показує список страв, POST видаляє.
    path(
        "categories/<int:pk>/delete/",
        CategoryDeleteView.as_view(),
        name="category_delete",
    ),
    # --- Теги (таска 1.8) --- #
    # TagListView.as_view() — CBV підключається через метод as_view().
    # as_view() повертає callable, який Django може використовувати як view-функцію.
    # Документація:
    #   https://docs.djangoproject.com/en/stable/ref/class-based-views/base/#django.views.generic.base.View.as_view
    path("tags/", TagListView.as_view(), name="tag_list"),
    # Створення тега через generic CreateView (таска 2.2)
    # ВАЖЛИВО: create/ ПЕРЕД <int:pk>/, щоб Django не сприйняв "create" як pk.
    # TagCreateView.as_view() — CBV підключається через as_view().
    # Документація:
    #   https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-editing/#createview
    path("tags/create/", TagCreateView.as_view(), name="tag_create"),
    # Редагування тега через generic UpdateView (таска 2.7)
    # <int:pk> — Django витягує pk з URL і передає у UpdateView.
    # UpdateView завантажує об'єкт: Tag.objects.get(pk=pk).
    # Документація:
    #   https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-editing/#updateview
    path("tags/<int:pk>/edit/", TagUpdateView.as_view(), name="tag_update"),
    # Видалення тега через generic DeleteView (таска 2.7)
    # GET — сторінка підтвердження, POST — видалення.
    # Документація:
    #   https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-editing/#deleteview
    path("tags/<int:pk>/delete/", TagDeleteView.as_view(), name="tag_delete"),
    # --- Пошук (таска 3.1) --- #
    # GET /menu/search/?q=борщ — пошук страв через Q-objects.
    # Документація:
    #   https://docs.djangoproject.com/en/stable/topics/db/queries/#complex-lookups-with-q-objects
    path("search/", dish_search, name="dish_search"),
    # --- Страви --- #
    path("dishes/", dish_list, name="dish_list"),
    # Створення страви через generic CreateView (таска 2.6)
    # ВАЖЛИВО: create/ ПЕРЕД <int:pk>/, щоб Django не сприйняв "create" як pk.
    # DishCreateView.as_view() — CBV підключається через as_view().
    # Документація:
    #   https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-editing/#createview
    path("dishes/create/", DishCreateView.as_view(), name="dish_create"),
    # Редагування страви через generic UpdateView (таска 2.7)
    # Найскладніший update: FK + M2M + зображення + formset.
    path("dishes/<int:pk>/edit/", DishUpdateView.as_view(), name="dish_update"),
    # Видалення страви через generic DeleteView (таска 2.7)
    # CASCADE видаляє DishMainImage та всі DishPicture.
    path("dishes/<int:pk>/delete/", DishDeleteView.as_view(), name="dish_delete"),
    path("dishes/<int:pk>/", dish_detail, name="dish_detail"),
]
