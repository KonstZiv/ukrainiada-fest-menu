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
    path(
        "order/<int:order_id>/confirm-payment/",
        waiter_views.order_confirm_payment,
        name="confirm_payment",
    ),
    path("senior/", waiter_views.senior_waiter_dashboard, name="senior_dashboard"),
    path(
        "senior/order/<int:order_id>/confirm-payment/",
        waiter_views.senior_confirm_payment,
        name="senior_confirm_payment",
    ),
]
