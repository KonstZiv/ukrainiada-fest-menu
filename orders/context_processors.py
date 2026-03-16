"""Context processors for order-related data available in all templates."""

from typing import Any

from django.http import HttpRequest

from orders.cart import cart_item_count, get_cart


def cart_context(request: HttpRequest) -> dict[str, Any]:
    """Provide cart_count and cart_quantities to all templates."""
    cart = get_cart(request)
    return {
        "cart_count": cart_item_count(request),
        "cart_quantities": {item["dish_id"]: item["quantity"] for item in cart},
    }
