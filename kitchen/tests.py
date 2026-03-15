from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

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
    django_user_model: Any,
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
    django_user_model: Any,
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


@pytest.mark.django_db
def test_kitchen_ticket_str() -> None:
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    order = Order.objects.create()
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(order_item=item)
    assert f"Ticket #{ticket.pk}" in str(ticket)
    assert "pending" in str(ticket)


# --- Dashboard tests ---


@pytest.mark.django_db
def test_kitchen_dashboard_requires_auth(client: Client) -> None:
    response = client.get("/kitchen/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_visitor_cannot_access_kitchen(client: Client, django_user_model: Any) -> None:
    visitor = django_user_model.objects.create_user(
        email="v@test.com", username="visitor", password="testpass123", role="visitor"
    )
    client.force_login(visitor)
    response = client.get("/kitchen/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_kitchen_user_sees_dashboard(client: Client, django_user_model: Any) -> None:
    kitchen = django_user_model.objects.create_user(
        email="k@test.com", username="cook", password="testpass123", role="kitchen"
    )
    client.force_login(kitchen)
    response = client.get("/kitchen/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_escalation_level_choices() -> None:
    assert KitchenTicket.EscalationLevel.NONE == 0
    assert KitchenTicket.EscalationLevel.SUPERVISOR == 1
    assert KitchenTicket.EscalationLevel.MANAGER == 2


def _make_dish_and_order() -> tuple[Dish, Order, OrderItem]:
    """Create a dish with an order item for testing."""
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="TestDish",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    order = Order.objects.create()
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    return dish, order, item


@pytest.mark.django_db
def test_supervisor_sees_escalated_tickets(
    client: Client, django_user_model: Any
) -> None:
    supervisor = django_user_model.objects.create_user(
        email="s@test.com",
        username="supervisor",
        password="testpass123",
        role="kitchen_supervisor",
    )
    client.force_login(supervisor)

    _, _, item1 = _make_dish_and_order()
    KitchenTicket.objects.create(
        order_item=item1,
        escalation_level=KitchenTicket.EscalationLevel.SUPERVISOR,
    )

    response = client.get("/kitchen/")
    assert response.status_code == 200
    assert b"TestDish" in response.content


@pytest.mark.django_db
def test_kitchen_sees_only_assigned_pending(
    client: Client, django_user_model: Any
) -> None:
    cook = django_user_model.objects.create_user(
        email="c@test.com", username="cook", password="testpass123", role="kitchen"
    )
    client.force_login(cook)

    dish_mine, _, item_mine = _make_dish_and_order()
    KitchenAssignment.objects.create(dish=dish_mine, kitchen_user=cook)
    KitchenTicket.objects.create(order_item=item_mine)

    # Unassigned dish — should not appear
    cat2 = Category.objects.create(title="Cat2", description="", number_in_line=2)
    dish_other = Dish.objects.create(
        title="OtherDish",
        description="",
        price=Decimal("3.00"),
        weight=100,
        calorie=100,
        category=cat2,
    )
    order2 = Order.objects.create()
    item_other = OrderItem.objects.create(order=order2, dish=dish_other, quantity=1)
    KitchenTicket.objects.create(order_item=item_other)

    response = client.get("/kitchen/")
    content = response.content.decode()
    assert "TestDish" in content
    assert "OtherDish" not in content


@pytest.mark.django_db
def test_my_taken_shows_only_mine(client: Client, django_user_model: Any) -> None:
    cook = django_user_model.objects.create_user(
        email="c@test.com", username="cook", password="testpass123", role="kitchen"
    )
    other = django_user_model.objects.create_user(
        email="o@test.com", username="other", password="testpass123", role="kitchen"
    )
    client.force_login(cook)

    _, _, item1 = _make_dish_and_order()
    KitchenTicket.objects.create(
        order_item=item1,
        status=KitchenTicket.Status.TAKEN,
        assigned_to=cook,
    )

    cat2 = Category.objects.create(title="Cat2", description="", number_in_line=2)
    dish2 = Dish.objects.create(
        title="OtherTaken",
        description="",
        price=Decimal("3.00"),
        weight=100,
        calorie=100,
        category=cat2,
    )
    order2 = Order.objects.create()
    item2 = OrderItem.objects.create(order=order2, dish=dish2, quantity=1)
    KitchenTicket.objects.create(
        order_item=item2,
        status=KitchenTicket.Status.TAKEN,
        assigned_to=other,
    )

    response = client.get("/kitchen/")
    content = response.content.decode()
    assert "TestDish" in content
    assert "OtherTaken" not in content
