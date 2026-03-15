# Task 2.2 — Взяти тікет в роботу і позначити готовим (детально)

## kitchen/services.py — додати

```python
from django.utils import timezone
from django.db import transaction
from kitchen.models import KitchenTicket


def take_ticket(ticket: KitchenTicket, kitchen_user) -> KitchenTicket:  # type: ignore[type-arg]
    """Кухар бере тікет в роботу.

    Raises:
        ValueError: якщо тікет не в статусі PENDING.
        ValueError: якщо тікет вже взятий іншим кухарем.
    """
    if ticket.status != KitchenTicket.Status.PENDING:
        raise ValueError(f"Cannot take ticket in status '{ticket.status}'")

    with transaction.atomic():
        # select_for_update — захист від race condition при одночасному взятті
        ticket = KitchenTicket.objects.select_for_update().get(pk=ticket.pk)
        if ticket.status != KitchenTicket.Status.PENDING:
            raise ValueError("Ticket was already taken by another cook")

        ticket.status = KitchenTicket.Status.TAKEN
        ticket.assigned_to = kitchen_user
        ticket.taken_at = timezone.now()
        ticket.save(update_fields=["status", "assigned_to", "taken_at"])

    return ticket


def mark_ticket_done(ticket: KitchenTicket, kitchen_user) -> KitchenTicket:  # type: ignore[type-arg]
    """Кухар позначає тікет як готовий.

    Raises:
        ValueError: якщо тікет не в статусі TAKEN.
        ValueError: якщо тікет взятий іншим кухарем.
    """
    if ticket.status != KitchenTicket.Status.TAKEN:
        raise ValueError(f"Cannot mark done ticket in status '{ticket.status}'")
    if ticket.assigned_to_id != kitchen_user.id:
        raise ValueError("Cannot mark done ticket assigned to another cook")

    ticket.status = KitchenTicket.Status.DONE
    ticket.done_at = timezone.now()
    ticket.save(update_fields=["status", "done_at"])

    # Перевіряємо чи всі тікети замовлення готові → оновлюємо Order.status
    _check_order_ready(ticket)

    return ticket


def _check_order_ready(ticket: KitchenTicket) -> None:
    """Якщо всі KitchenTicket для замовлення DONE — Order переходить в READY."""
    from orders.models import Order
    order = ticket.order_item.order
    all_done = not KitchenTicket.objects.filter(
        order_item__order=order,
    ).exclude(status=KitchenTicket.Status.DONE).exists()

    if all_done:
        order.status = Order.Status.READY
        order.ready_at = timezone.now()
        order.save(update_fields=["status", "ready_at", "updated_at"])
```

## kitchen/views.py — додати

```python
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages


@role_required(*KITCHEN_ROLES)
@require_POST
def ticket_take(request: HttpRequest, ticket_id: int) -> HttpResponse:
    ticket = get_object_or_404(KitchenTicket, pk=ticket_id)
    try:
        take_ticket(ticket, kitchen_user=request.user)
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("kitchen:dashboard")


@role_required(*KITCHEN_ROLES)
@require_POST
def ticket_done(request: HttpRequest, ticket_id: int) -> HttpResponse:
    ticket = get_object_or_404(KitchenTicket, pk=ticket_id)
    try:
        mark_ticket_done(ticket, kitchen_user=request.user)
        messages.success(request, f"Страва '{ticket.order_item.dish.title}' готова!")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("kitchen:dashboard")
```

## Тести

```python
# kitchen/tests/test_services.py
import pytest
from decimal import Decimal


@pytest.mark.tier2
@pytest.mark.django_db
def test_take_ticket_success(django_user_model):
    from kitchen.services import take_ticket
    from kitchen.models import KitchenTicket
    from orders.models import Order, OrderItem
    from menu.models import Category, Dish

    kitchen_user = django_user_model.objects.create_user(
        email="k@test.com", password="pass", role="kitchen"
    )
    cat = Category.objects.create(title="C", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D", description="", price=Decimal("5.00"), weight=100, calorie=100, category=cat
    )
    order = Order.objects.create(status="approved")
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(order_item=item)

    result = take_ticket(ticket, kitchen_user=kitchen_user)

    assert result.status == KitchenTicket.Status.TAKEN
    assert result.assigned_to == kitchen_user
    assert result.taken_at is not None


@pytest.mark.tier2
@pytest.mark.django_db
def test_take_ticket_race_condition(django_user_model):
    """select_for_update захищає від одночасного взяття двома кухарями."""
    from kitchen.services import take_ticket
    from kitchen.models import KitchenTicket
    from orders.models import Order, OrderItem
    from menu.models import Category, Dish

    k1 = django_user_model.objects.create_user(email="k1@test.com", password="pass", role="kitchen")
    k2 = django_user_model.objects.create_user(email="k2@test.com", password="pass", role="kitchen")
    cat = Category.objects.create(title="C", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D", description="", price=Decimal("5.00"), weight=100, calorie=100, category=cat
    )
    order = Order.objects.create(status="approved")
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(order_item=item)

    take_ticket(ticket, kitchen_user=k1)
    ticket.refresh_from_db()

    with pytest.raises(ValueError):
        take_ticket(ticket, kitchen_user=k2)


@pytest.mark.tier2
@pytest.mark.django_db
def test_all_tickets_done_sets_order_ready(django_user_model):
    from kitchen.services import take_ticket, mark_ticket_done
    from kitchen.models import KitchenTicket
    from orders.models import Order, OrderItem
    from menu.models import Category, Dish

    kitchen_user = django_user_model.objects.create_user(
        email="k@test.com", password="pass", role="kitchen"
    )
    cat = Category.objects.create(title="C", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D", description="", price=Decimal("5.00"), weight=100, calorie=100, category=cat
    )
    order = Order.objects.create(status="approved")
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(order_item=item)

    take_ticket(ticket, kitchen_user=kitchen_user)
    mark_ticket_done(ticket, kitchen_user=kitchen_user)

    order.refresh_from_db()
    assert order.status == Order.Status.READY
```

## Acceptance criteria

- [ ] `take_ticket` — `select_for_update`, захист від race condition
- [ ] `mark_ticket_done` — перевіряє що кухар є assigned_to
- [ ] Коли всі тікети `DONE` → `Order.status = READY` автоматично
- [ ] POST-only views для take і done
- [ ] Тести зелені
