"""Context processors for order-related data available in all templates."""

from decimal import Decimal
from typing import Any

from django.http import HttpRequest

from menu.models import Dish
from orders.cart import cart_item_count, get_cart


def cart_context(request: HttpRequest) -> dict[str, Any]:
    """Provide cart_count, cart_total, and cart_quantities to all templates."""
    cart = get_cart(request)
    quantities: dict[int, int] = {item["dish_id"]: item["quantity"] for item in cart}

    total = Decimal("0")
    if quantities:
        dishes = {d.id: d.price for d in Dish.objects.filter(id__in=quantities.keys())}
        total = sum(
            (dishes.get(did, Decimal("0")) * qty for did, qty in quantities.items()),
            Decimal("0"),
        )

    return {
        "cart_count": cart_item_count(request),
        "cart_total": total,
        "cart_quantities": quantities,
    }


def manager_context(request: HttpRequest) -> dict[str, int]:
    """Provide open escalation count for manager navbar badge."""
    if not hasattr(request, "user") or not request.user.is_authenticated:
        return {}
    if getattr(request.user, "role", None) != "manager":
        return {}

    from orders.models import StepEscalation, VisitorEscalation

    visitor = VisitorEscalation.objects.filter(
        status__in=[
            VisitorEscalation.Status.OPEN,
            VisitorEscalation.Status.ACKNOWLEDGED,
        ],
    ).count()
    step = StepEscalation.objects.filter(
        level=StepEscalation.Level.MANAGER,
        resolved_at__isnull=True,
    ).count()
    return {
        "manager_escalation_count": visitor + step,
    }
