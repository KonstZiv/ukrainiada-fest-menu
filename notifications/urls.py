from django.urls import path

from notifications import views

app_name = "notifications"

urlpatterns = [
    path("stream/", views.user_events, name="user_events"),
    path("visitor/<int:order_id>/", views.visitor_order_events, name="visitor_sse"),
]
