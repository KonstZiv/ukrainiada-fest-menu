from django.urls import path

from orders import waiter_views

app_name = "waiter"

urlpatterns = [
    path("orders/", waiter_views.waiter_order_list, name="order_list"),
    path("order/<int:order_id>/scan/", waiter_views.order_scan, name="order_scan"),
    path(
        "order/<int:order_id>/approve/",
        waiter_views.order_approve,
        name="order_approve",
    ),
    path("dashboard/", waiter_views.waiter_dashboard, name="dashboard"),
    path(
        "order/<int:order_id>/delivered/",
        waiter_views.order_mark_delivered,
        name="order_delivered",
    ),
]
