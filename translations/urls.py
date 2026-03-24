"""URL patterns for translation review workflow."""

from django.urls import path

from translations import views

app_name = "translations"

urlpatterns = [
    path("review/", views.review_list, name="review"),
    path("approve/<int:pk>/", views.approve_single, name="approve"),
    path("approve-all/", views.approve_all, name="approve_all"),
    path("edit/<int:pk>/", views.edit_translation, name="edit"),
    path("retry/<int:pk>/", views.retry_failed, name="retry"),
]
