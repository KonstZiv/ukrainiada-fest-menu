"""Kitchen business logic — ticket creation, actions, retrieval."""

from __future__ import annotations

import logging
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
from orders.escalation_ownership import resolve_step_escalations
from orders.event_log import log_event
from orders.models import Order, StepEscalation

if TYPE_CHECKING:
    from user.models import User

logger = logging.getLogger("notifications")


def _activate_order(order: Order) -> None:
    """Transition order VERIFIED → IN_PROGRESS on first ticket take."""
    if order.status == Order.Status.VERIFIED:
        order.status = Order.Status.IN_PROGRESS
        order.save(update_fields=["status"])


def create_tickets_for_order(order: Order) -> list[KitchenTicket]:
    """Create one KitchenTicket per portion (quantity) of each OrderItem.

    Called from orders/services.py::verify_order().
    Does not check order status — caller's responsibility.
    """
    tickets = [
        KitchenTicket(order_item=item)
        for item in order.items.select_related("dish").all()
        for _ in range(item.quantity)
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
    logger.info(
        "[kitchen:take] ticket=%d cook=%s status=%s",
        ticket.pk,
        kitchen_user.staff_label,
        ticket.status,
    )
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

    _activate_order(order)
    resolve_step_escalations(StepEscalation.Step.PENDING_TAKEN, ticket=ticket)

    log_event(
        order,
        f"Кухня: {kitchen_user.staff_label} прийняв(ла) в роботу {dish_title}",
        actor_label=kitchen_user.staff_label,
        actor=kitchen_user,
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


def mark_ticket_done(
    ticket: KitchenTicket, kitchen_user: User
) -> tuple[KitchenTicket, list[str]]:
    """Kitchen staff marks a ticket as done.

    Supports soft flow: if ticket is PENDING, auto-takes it first.
    Automatically checks if all tickets for the order are done
    and updates Order.status to READY.

    Returns:
        Tuple of (ticket, skipped_steps) where skipped_steps lists
        auto-skipped flow steps (empty if none were skipped).

    Raises:
        ValueError: if ticket is already DONE or assigned to another cook.

    """
    logger.info(
        "[kitchen:done] ticket=%d cook=%s status=%s",
        ticket.pk,
        kitchen_user.staff_label,
        ticket.status,
    )
    skipped: list[str] = []

    if ticket.status == KitchenTicket.Status.DONE:
        msg = "Ticket is already done"
        raise ValueError(msg)

    if (
        ticket.status == KitchenTicket.Status.TAKEN
        and ticket.assigned_to_id != kitchen_user.id
    ):
        msg = "Cannot mark done ticket assigned to another cook"
        raise ValueError(msg)

    # Soft flow: auto-take if PENDING
    if ticket.status == KitchenTicket.Status.PENDING:
        now = timezone.now()
        with transaction.atomic():
            ticket = KitchenTicket.objects.select_for_update().get(pk=ticket.pk)
            if ticket.status == KitchenTicket.Status.PENDING:
                ticket.assigned_to = kitchen_user
                ticket.taken_at = now
                ticket.status = KitchenTicket.Status.TAKEN
                ticket.save(update_fields=["status", "assigned_to", "taken_at"])
                skipped.append("Взяти в роботу")

        dish_title = ticket.order_item.dish.title
        order = ticket.order_item.order

        _activate_order(order)

        log_event(
            order,
            f"⚠️ Авто: {kitchen_user.staff_label} пропустив(ла) крок "
            f"'Взяти' для {dish_title}",
            actor_label=kitchen_user.staff_label,
            actor=kitchen_user,
            is_auto_skip=True,
        )

    ticket.status = KitchenTicket.Status.DONE
    ticket.done_at = timezone.now()
    ticket.save(update_fields=["status", "done_at"])

    resolve_step_escalations(StepEscalation.Step.TAKEN_DONE, ticket=ticket)

    dish_title = ticket.order_item.dish.title
    order = ticket.order_item.order
    log_event(
        order,
        f"Кухня: {kitchen_user.staff_label} приготував(ла) {dish_title} ✅",
        actor_label=kitchen_user.staff_label,
        actor=kitchen_user,
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
    logger.info(
        "[kitchen:done] DONE ticket=%d order_ready=%s skipped=%s",
        ticket.pk,
        order_ready,
        skipped,
    )
    if order_ready:
        log_event(order, "Усі страви готові! Очікуємо офіціанта для доставки 🍽️")
        if waiter_id:
            push_order_ready(order_id=order.id, waiter_id=waiter_id)

    return ticket, skipped


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
    """Cook confirms dish was physically handed to waiter.

    Marks ticket as delivered (removes from kitchen "Готово" tab).
    Cancels any pending QR-based handoff.
    Auto-transitions order to DELIVERED when all tickets handed off.

    Raises:
        ValueError: if ticket is not DONE or not assigned to this cook.

    """
    logger.info(
        "[kitchen:handoff] ticket=%d cook=%s status=%s",
        ticket.pk,
        kitchen_user.staff_label,
        ticket.status,
    )
    if ticket.status != KitchenTicket.Status.DONE:
        msg = f"Cannot handoff ticket in status '{ticket.status}'"
        raise ValueError(msg)
    if ticket.assigned_to_id != kitchen_user.id:
        msg = "Only the assigned cook can confirm handoff"
        raise ValueError(msg)

    now = timezone.now()

    # Mark as handed off (dish moved: kitchen → waiter)
    if not ticket.handed_off_at:
        ticket.handed_off_at = now
        ticket.save(update_fields=["handed_off_at"])

        resolve_step_escalations(StepEscalation.Step.DONE_HANDOFF, ticket=ticket)

        dish_title = ticket.order_item.dish.title
        order = ticket.order_item.order
        log_event(
            order,
            f"Кухня: {kitchen_user.staff_label} передав(ла) {dish_title} офіціанту",
            actor_label=kitchen_user.staff_label,
            actor=kitchen_user,
        )
        push_visitor_event(
            order_id=order.id,
            event_type="dish_collecting",
            data={"dish": dish_title, "cook_label": kitchen_user.staff_label},
        )

    # Cancel any pending QR-based handoff
    KitchenHandoff.objects.filter(ticket=ticket, is_confirmed=False).update(
        is_confirmed=True, confirmed_at=now
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
