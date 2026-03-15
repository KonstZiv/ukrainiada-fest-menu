"""Session-based cart for anonymous and authenticated visitors."""

from __future__ import annotations

from typing import TypedDict

from django.http import HttpRequest

CART_SESSION_KEY = "festival_cart"


class CartItem(TypedDict):
    dish_id: int
    quantity: int


def get_cart(request: HttpRequest) -> list[CartItem]:
    """Return current cart contents from session."""
    return list(request.session.get(CART_SESSION_KEY, []))


def add_to_cart(request: HttpRequest, dish_id: int, quantity: int = 1) -> None:
    """Add a dish to cart or increment quantity if already present."""
    cart = get_cart(request)
    for item in cart:
        if item["dish_id"] == dish_id:
            item["quantity"] += quantity
            request.session[CART_SESSION_KEY] = cart
            request.session.modified = True
            return
    cart.append({"dish_id": dish_id, "quantity": quantity})
    request.session[CART_SESSION_KEY] = cart
    request.session.modified = True


def remove_from_cart(request: HttpRequest, dish_id: int) -> None:
    """Remove a dish from cart entirely."""
    cart = [item for item in get_cart(request) if item["dish_id"] != dish_id]
    request.session[CART_SESSION_KEY] = cart
    request.session.modified = True


def clear_cart(request: HttpRequest) -> None:
    """Remove all items from cart."""
    request.session.pop(CART_SESSION_KEY, None)
    request.session.modified = True


def cart_item_count(request: HttpRequest) -> int:
    """Return total number of items in cart."""
    return sum(item["quantity"] for item in get_cart(request))
