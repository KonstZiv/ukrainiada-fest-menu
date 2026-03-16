"""Context processors for order-related data available in all templates."""

from django.http import HttpRequest

from orders.cart import cart_item_count


def cart_context(request: HttpRequest) -> dict[str, int]:
    """Provide cart_count to all templates."""
    return {"cart_count": cart_item_count(request)}
