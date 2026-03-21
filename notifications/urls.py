from django.urls import path

from notifications import views

app_name = "notifications"

urlpatterns = [
    path("stream/", views.sse_stream, name="sse_stream"),
    path("visitor/<int:order_id>/", views.sse_stream, name="visitor_sse"),
]
