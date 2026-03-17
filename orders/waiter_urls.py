from django.urls import path

from orders import waiter_views

app_name = "waiter"

urlpatterns = [
    path("orders/", waiter_views.waiter_order_list, name="order_list"),
    path("order/<int:order_id>/scan/", waiter_views.order_scan, name="order_scan"),
    path(
        "order/<int:order_id>/accept/",
        waiter_views.order_accept,
        name="order_accept",
    ),
    path(
        "order/<int:order_id>/verify/",
        waiter_views.order_verify,
        name="order_verify",
    ),
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
    path(
        "handoff/<uuid:token>/confirm/",
        waiter_views.handoff_confirm_view,
        name="handoff_confirm",
    ),
    path(
        "escalation/<int:escalation_id>/ack/",
        waiter_views.escalation_acknowledge,
        name="escalation_acknowledge",
    ),
    path(
        "escalation/<int:escalation_id>/resolve/",
        waiter_views.escalation_resolve,
        name="escalation_resolve",
    ),
    path("senior/", waiter_views.senior_waiter_dashboard, name="senior_dashboard"),
    path(
        "senior/order/<int:order_id>/confirm-payment/",
        waiter_views.senior_confirm_payment,
        name="senior_confirm_payment",
    ),
]
