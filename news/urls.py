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
    path(
        "<int:pk>/translation-feedback/",
        views.submit_translation_feedback,
        name="translation_feedback",
    ),
    path("<int:pk>/comment/", views.submit_comment, name="submit_comment"),
    path("comments/moderate/", views.moderate_comments, name="moderate_comments"),
    path("comments/<int:pk>/approve/", views.approve_comment, name="approve_comment"),
    path("comments/<int:pk>/reject/", views.reject_comment, name="reject_comment"),
]
