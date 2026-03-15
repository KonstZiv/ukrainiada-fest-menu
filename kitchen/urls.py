from django.urls import path

from kitchen import views

app_name = "kitchen"

urlpatterns = [
    path("", views.kitchen_dashboard, name="dashboard"),
]
