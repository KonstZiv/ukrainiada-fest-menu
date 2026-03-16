from django.urls import path

from kitchen import views

app_name = "kitchen"

urlpatterns = [
    path("", views.kitchen_dashboard, name="dashboard"),
    path("ticket/<int:ticket_id>/take/", views.ticket_take, name="ticket_take"),
    path("ticket/<int:ticket_id>/done/", views.ticket_done, name="ticket_done"),
    path(
        "ticket/<int:ticket_id>/handoff/",
        views.generate_handoff_qr,
        name="handoff_qr",
    ),
]
