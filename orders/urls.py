from django.urls import path

from orders import views

app_name = "orders"

urlpatterns = [
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/", views.cart_add, name="cart_add"),
    path("cart/remove/<int:dish_id>/", views.cart_remove, name="cart_remove"),
    path("cart/decrease/<int:dish_id>/", views.cart_decrease, name="cart_decrease"),
    path("history/", views.order_history, name="order_history"),
    path("submit/", views.order_submit, name="order_submit"),
    path("<int:order_id>/", views.order_detail, name="order_detail"),
    path("<int:order_id>/qr/", views.order_qr, name="order_qr"),
    path("<int:order_id>/pay/", views.order_pay_online, name="order_pay"),
    path(
        "<int:order_id>/escalate/",
        views.create_escalation_view,
        name="escalate",
    ),
]
