from decimal import Decimal

import pytest

from kitchen.models import KitchenAssignment, KitchenTicket
from kitchen.services import create_tickets_for_order, get_pending_tickets_for_user
from menu.models import Category, Dish
from orders.models import Order, OrderItem


def test_kitchen_ticket_status_choices() -> None:
    statuses = {s.value for s in KitchenTicket.Status}
    assert statuses == {"pending", "taken", "done"}


def test_kitchen_ticket_default_status() -> None:
    ticket = KitchenTicket()
    assert ticket.status == KitchenTicket.Status.PENDING


@pytest.mark.django_db
def test_create_tickets_for_order() -> None:
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish1 = Dish.objects.create(
        title="D1",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    dish2 = Dish.objects.create(
        title="D2",
        description="",
        price=Decimal("3.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    order = Order.objects.create()
    OrderItem.objects.create(order=order, dish=dish1, quantity=1)
    OrderItem.objects.create(order=order, dish=dish2, quantity=2)

    tickets = create_tickets_for_order(order)

    assert len(tickets) == 2
    assert all(t.status == KitchenTicket.Status.PENDING for t in tickets)
    assert KitchenTicket.objects.filter(order_item__order=order).count() == 2


@pytest.mark.django_db
def test_get_pending_tickets_filtered_by_assignment(
    django_user_model,  # type: ignore[no-untyped-def]
) -> None:
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish_mine = Dish.objects.create(
        title="Mine",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    dish_other = Dish.objects.create(
        title="Other",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    kitchen_user = django_user_model.objects.create_user(
        email="k@test.com", username="ktest", password="testpass123", role="kitchen"
    )
    KitchenAssignment.objects.create(dish=dish_mine, kitchen_user=kitchen_user)

    order = Order.objects.create()
    OrderItem.objects.create(order=order, dish=dish_mine, quantity=1)
    OrderItem.objects.create(order=order, dish=dish_other, quantity=1)
    create_tickets_for_order(order)

    tickets = get_pending_tickets_for_user(kitchen_user.id)
    dish_titles = {t.order_item.dish.title for t in tickets}
    assert "Mine" in dish_titles
    assert "Other" not in dish_titles


@pytest.mark.django_db
def test_kitchen_assignment_str(
    django_user_model,  # type: ignore[no-untyped-def]
) -> None:
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="Борщ",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    user = django_user_model.objects.create_user(
        email="chef@test.com", username="chef", password="testpass123", role="kitchen"
    )
    assignment = KitchenAssignment.objects.create(dish=dish, kitchen_user=user)
    assert "Борщ" in str(assignment)
    assert "chef@test.com" in str(assignment)
