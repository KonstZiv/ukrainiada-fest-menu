from django.urls import path

from notifications import views

app_name = "notifications"

urlpatterns = [
    path("stream/", views.user_events, name="user_events"),
]
