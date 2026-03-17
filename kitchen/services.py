"""Kitchen business logic — ticket creation, actions, retrieval."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from kitchen.models import KitchenAssignment, KitchenHandoff, KitchenTicket
from notifications.events import (
    push_order_ready,
    push_ticket_done,
    push_ticket_taken,
    push_visitor_event,
)
from orders.event_log import log_event
from orders.models import Order

if TYPE_CHECKING:
    from user.models import User


def create_tickets_for_order(order: Order) -> list[KitchenTicket]:
    """Create a KitchenTicket for each OrderItem.

    Called from orders/services.py::approve_order().
    Does not check order status — caller's responsibility.
    """
    tickets = [
        KitchenTicket(order_item=item)
        for item in order.items.select_related("dish").all()
    ]
    return KitchenTicket.objects.bulk_create(tickets)


def get_pending_tickets_for_user(kitchen_user_id: int) -> QuerySet[KitchenTicket]:
    """Return PENDING tickets for dishes assigned to this kitchen user.

    If a dish has no KitchenAssignment, it is NOT visible
    (only explicitly assigned dishes are returned).
    """
    assigned_dish_ids = KitchenAssignment.objects.filter(
        kitchen_user_id=kitchen_user_id
    ).values_list("dish_id", flat=True)

    return KitchenTicket.objects.filter(
        status=KitchenTicket.Status.PENDING,
        order_item__dish_id__in=assigned_dish_ids,
    ).select_related("order_item__dish", "order_item__order")


def take_ticket(ticket: KitchenTicket, kitchen_user: User) -> KitchenTicket:
    """Kitchen staff picks up a ticket.

    Uses select_for_update to prevent race conditions.

    Raises:
        ValueError: if ticket is not PENDING or already taken.

    """
    if ticket.status != KitchenTicket.Status.PENDING:
        msg = f"Cannot take ticket in status '{ticket.status}'"
        raise ValueError(msg)

    with transaction.atomic():
        ticket = KitchenTicket.objects.select_for_update().get(pk=ticket.pk)
        if ticket.status != KitchenTicket.Status.PENDING:
            msg = "Ticket was already taken by another cook"
            raise ValueError(msg)

        ticket.status = KitchenTicket.Status.TAKEN
        ticket.assigned_to = kitchen_user
        ticket.taken_at = timezone.now()
        ticket.save(update_fields=["status", "assigned_to", "taken_at"])

    dish_title = ticket.order_item.dish.title
    order = ticket.order_item.order
    log_event(
        order,
        f"Кухня: {kitchen_user.staff_label} прийняв(ла) в роботу {dish_title}",
        actor_label=kitchen_user.staff_label,
    )

    waiter_id = order.waiter_id
    if waiter_id:
        cook_name = kitchen_user.get_full_name() or kitchen_user.email
        push_ticket_taken(
            ticket_id=ticket.pk,
            waiter_id=waiter_id,
            kitchen_user_name=cook_name,
        )

    # Notify visitor
    push_visitor_event(
        order_id=order.id,
        event_type="ticket_taken",
        data={
            "ticket_id": ticket.pk,
            "dish": dish_title[:40],
            "cook_label": kitchen_user.staff_label,
        },
    )

    return ticket


def mark_ticket_done(ticket: KitchenTicket, kitchen_user: User) -> KitchenTicket:
    """Kitchen staff marks a ticket as done.

    Automatically checks if all tickets for the order are done
    and updates Order.status to READY.

    Raises:
        ValueError: if ticket is not TAKEN or assigned to another cook.

    """
    if ticket.status != KitchenTicket.Status.TAKEN:
        msg = f"Cannot mark done ticket in status '{ticket.status}'"
        raise ValueError(msg)
    if ticket.assigned_to_id != kitchen_user.id:
        msg = "Cannot mark done ticket assigned to another cook"
        raise ValueError(msg)

    ticket.status = KitchenTicket.Status.DONE
    ticket.done_at = timezone.now()
    ticket.save(update_fields=["status", "done_at"])

    dish_title = ticket.order_item.dish.title
    order = ticket.order_item.order
    log_event(
        order,
        f"Кухня: {kitchen_user.staff_label} приготував(ла) {dish_title} ✅",
        actor_label=kitchen_user.staff_label,
    )

    waiter_id = order.waiter_id
    if waiter_id:
        push_ticket_done(
            ticket_id=ticket.pk,
            order_id=order.id,
            waiter_id=waiter_id,
            dish_title=dish_title,
        )

    # Notify visitor
    push_visitor_event(
        order_id=order.id,
        event_type="ticket_done",
        data={
            "ticket_id": ticket.pk,
            "dish": dish_title[:40],
            "cook_label": kitchen_user.staff_label,
        },
    )

    order_ready = _check_order_ready(ticket)
    if order_ready:
        log_event(order, "Усі страви готові! Очікуємо офіціанта для доставки 🍽️")
        if waiter_id:
            push_order_ready(order_id=order.id, waiter_id=waiter_id)

    return ticket


def create_handoff(ticket: KitchenTicket, target_waiter: User) -> KitchenHandoff:
    """Create a one-time handoff token for dish transfer to waiter.

    Removes any existing unconfirmed handoff for this ticket before
    creating a new one (e.g. expired QR regeneration).

    Raises:
        ValueError: if ticket is not in DONE status or already has
            a confirmed handoff.

    """
    if ticket.status != KitchenTicket.Status.DONE:
        msg = f"Cannot handoff ticket in status '{ticket.status}'"
        raise ValueError(msg)

    # Remove old unconfirmed handoff if any
    KitchenHandoff.objects.filter(ticket=ticket, is_confirmed=False).delete()

    return KitchenHandoff.objects.create(
        ticket=ticket,
        target_waiter=target_waiter,
    )


def manual_handoff(ticket: KitchenTicket, kitchen_user: User) -> None:
    """One-sided handoff confirmation without QR scan.

    Used as fallback when the waiter cannot scan the QR code.
    Cancels any pending (unconfirmed) QR-based handoff for this ticket.
    Idempotent — safe to call multiple times.

    Raises:
        ValueError: if ticket is not DONE or not assigned to this cook.

    """
    if ticket.status != KitchenTicket.Status.DONE:
        msg = f"Cannot handoff ticket in status '{ticket.status}'"
        raise ValueError(msg)
    if ticket.assigned_to_id != kitchen_user.id:
        msg = "Only the assigned cook can confirm handoff"
        raise ValueError(msg)

    # Cancel any pending QR-based handoff
    KitchenHandoff.objects.filter(ticket=ticket, is_confirmed=False).update(
        is_confirmed=True, confirmed_at=timezone.now()
    )


def _check_order_ready(ticket: KitchenTicket) -> bool:
    """If all KitchenTickets for the order are DONE, set Order to READY."""
    order = ticket.order_item.order
    all_done = not (
        KitchenTicket.objects.filter(order_item__order=order)
        .exclude(status=KitchenTicket.Status.DONE)
        .exists()
    )

    if all_done:
        order.status = Order.Status.READY
        order.ready_at = timezone.now()
        order.save(update_fields=["status", "ready_at"])
        push_visitor_event(
            order_id=order.id,
            event_type="order_ready",
            data={"order_id": order.id},
        )

    return all_done
