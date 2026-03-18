from django.urls import path

from orders import manager_views

app_name = "manager"

urlpatterns = [
    path("", manager_views.manager_dashboard, name="dashboard"),
]
