"""URL patterns for news app."""

from django.urls import path

from news import views

app_name = "news"

urlpatterns = [
    path("", views.article_list, name="article_list"),
    path("<int:pk>/", views.article_detail, name="article_detail"),
    path("create/", views.ArticleCreateView.as_view(), name="article_create"),
    path("<int:pk>/edit/", views.ArticleUpdateView.as_view(), name="article_update"),
    path("<int:pk>/delete/", views.ArticleDeleteView.as_view(), name="article_delete"),
]
