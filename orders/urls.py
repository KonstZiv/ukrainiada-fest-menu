from django.urls import path

from orders import views

app_name = "orders"

urlpatterns = [
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/", views.cart_add, name="cart_add"),
    path("cart/remove/<int:dish_id>/", views.cart_remove, name="cart_remove"),
    path("submit/", views.order_submit, name="order_submit"),
    path("<int:order_id>/", views.order_detail, name="order_detail"),
]
