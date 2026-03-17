"""Waiter-facing views: order list, scan, approve, dashboard, deliver, senior."""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.db import models, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core_settings.types import AuthenticatedHttpRequest
from kitchen.models import KitchenHandoff
from kitchen.stats import get_dish_queue_stats
from notifications.events import push_visitor_event
from orders.escalation_services import acknowledge_escalation, resolve_escalation
from orders.models import Order, VisitorEscalation
from orders.services import (
    accept_order,
    approve_order,
    confirm_cash_payment,
    confirm_payment_by_senior,
    deliver_order,
    verify_order,
)
from user.decorators import role_required

WAITER_ROLES = ("waiter", "senior_waiter", "manager")


@role_required(*WAITER_ROLES)
def waiter_order_list(request: AuthenticatedHttpRequest) -> HttpResponse:
    """Waiter board — two tabs: new (unclaimed) + my orders."""
    new_orders = (
        Order.objects.filter(status=Order.Status.SUBMITTED)
        .prefetch_related("items__dish")
        .order_by("created_at")
    )
    my_orders_qs = (
        Order.objects.filter(
            waiter=request.user,
            status__in=[
                Order.Status.ACCEPTED,
                Order.Status.VERIFIED,
                Order.Status.IN_PROGRESS,
                Order.Status.READY,
            ],
        )
        .prefetch_related(
            "items__dish",
            "items__kitchen_ticket",
            "items__kitchen_ticket__assigned_to",
        )
        .order_by("created_at")
    )

    # Build per-order dish/ticket stats
    now = timezone.now()
    pickup_warn = settings.DISH_PICKUP_WARN  # minutes
    pickup_critical = settings.DISH_PICKUP_CRITICAL  # minutes
    my_orders_enriched = []
    my_ready_count = 0
    for order in my_orders_qs:
        tickets = []
        total_dishes = 0
        done_dishes = 0
        taken_dishes = 0
        has_overdue = False
        for item in order.items.all():
            total_dishes += 1
            ticket = getattr(item, "kitchen_ticket", None)
            status = ticket.status if ticket else "pending"
            done_min = 0
            dish_urgency = "normal"
            if status == "done":
                done_dishes += 1
                if ticket and ticket.done_at:
                    done_min = int((now - ticket.done_at).total_seconds() / 60)
                    if done_min >= pickup_critical:
                        dish_urgency = "critical"
                        has_overdue = True
                    elif done_min >= pickup_warn:
                        dish_urgency = "warn"
                        has_overdue = True
            elif status == "taken":
                taken_dishes += 1
            tickets.append(
                {
                    "dish_title": item.dish.title,
                    "quantity": item.quantity,
                    "subtotal": item.subtotal,
                    "status": status,
                    "cook_label": (
                        ticket.assigned_to.staff_label
                        if ticket and ticket.assigned_to
                        else None
                    ),
                    "done_min": done_min,
                    "dish_urgency": dish_urgency,
                }
            )
        if order.status == Order.Status.READY:
            my_ready_count += 1
        my_orders_enriched.append(
            {
                "order": order,
                "tickets": tickets,
                "total_dishes": total_dishes,
                "done_dishes": done_dishes,
                "taken_dishes": taken_dishes,
                "has_overdue": has_overdue,
            }
        )
    # Unpaid delivered
    unpaid_delivered = (
        Order.objects.filter(
            waiter=request.user,
            status=Order.Status.DELIVERED,
            payment_status=Order.PaymentStatus.UNPAID,
        )
        .prefetch_related("items__dish")
        .order_by("delivered_at")
    )

    # Cash on hand — sum of cash-paid orders for this waiter today
    cash_orders = Order.objects.filter(
        waiter=request.user,
        payment_status=Order.PaymentStatus.PAID,
        payment_method=Order.PaymentMethod.CASH,
    ).prefetch_related("items__dish")
    cash_total = sum(
        (o.total_price for o in cash_orders),
        Decimal("0"),
    )

    dish_stats = get_dish_queue_stats()
    tab = request.GET.get("tab", "new")

    # Annotate new orders with wait time for urgency display
    now = timezone.now()
    esc_threshold = settings.ESCALATION_MIN_WAIT  # minutes
    new_orders_with_wait = []
    for order in new_orders:
        wait_min = int((now - order.created_at).total_seconds() / 60)
        if wait_min >= esc_threshold * 2:
            urgency = "critical"
        elif wait_min >= esc_threshold:
            urgency = "overdue"
        else:
            urgency = "normal"
        new_orders_with_wait.append(
            {"order": order, "wait_min": wait_min, "urgency": urgency}
        )

    return render(
        request,
        "orders/waiter_order_list.html",
        {
            "new_orders_with_wait": new_orders_with_wait,
            "my_orders": my_orders_enriched,
            "unpaid_delivered": unpaid_delivered,
            "new_count": len(new_orders_with_wait),
            "my_count": len(my_orders_enriched),
            "my_ready_count": my_ready_count,
            "cash_total": cash_total,
            "cash_orders": cash_orders,
            "dish_stats": dish_stats,
            "active_tab": tab,
        },
    )


@role_required(*WAITER_ROLES)
def order_scan(request: AuthenticatedHttpRequest, order_id: int) -> HttpResponse:
    """Waiter scans QR — redirects to order detail for approval."""
    order = get_object_or_404(Order, pk=order_id)
    return render(request, "orders/waiter_order_detail.html", {"order": order})


@role_required(*WAITER_ROLES)
@require_POST
def order_accept(request: AuthenticatedHttpRequest, order_id: int) -> HttpResponse:
    """Waiter takes (accepts) a SUBMITTED order."""
    order = get_object_or_404(Order, pk=order_id)
    try:
        accept_order(order, request.user)
        messages.success(request, f"Замовлення #{order.id} — тепер ваше.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("waiter:order_scan", order_id=order.id)


@role_required(*WAITER_ROLES)
@require_POST
def order_verify(request: AuthenticatedHttpRequest, order_id: int) -> HttpResponse:
    """Waiter verifies an ACCEPTED order — sends to kitchen."""
    order = get_object_or_404(Order, pk=order_id)
    try:
        verify_order(order, request.user)
        messages.success(
            request, f"Замовлення #{order.id} верифіковано і передано на кухню."
        )
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("waiter:order_scan", order_id=order.id)


@role_required(*WAITER_ROLES)
@require_POST
def order_approve(request: AuthenticatedHttpRequest, order_id: int) -> HttpResponse:
    """Legacy: accept + verify in one step."""
    order = get_object_or_404(Order, pk=order_id)
    try:
        approve_order(order, request.user)
        messages.success(request, f"Замовлення #{order.id} підтверджено.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("waiter:order_scan", order_id=order.id)


@role_required(*WAITER_ROLES)
def waiter_dashboard(request: AuthenticatedHttpRequest) -> HttpResponse:
    """Waiter dashboard — own active orders with kitchen ticket status."""
    active_statuses = [
        Order.Status.ACCEPTED,
        Order.Status.VERIFIED,
        Order.Status.IN_PROGRESS,
        Order.Status.READY,
    ]
    orders = (
        Order.objects.filter(waiter=request.user, status__in=active_statuses)
        .select_related("visitor")
        .prefetch_related(
            "items__dish",
            "items__kitchen_ticket",
            "items__kitchen_ticket__assigned_to",
        )
        .annotate(
            total_annotated=models.Sum(
                models.F("items__dish__price") * models.F("items__quantity"),
                output_field=models.DecimalField(),
            )
        )
        .order_by("created_at")
    )
    my_escalations = (
        VisitorEscalation.objects.filter(
            order__waiter=request.user,
            status__in=["open", "acknowledged"],
        )
        .select_related("order")
        .order_by("created_at")
    )

    # Delivered but unpaid — show payment reminder
    unpaid_delivered = Order.objects.filter(
        waiter=request.user,
        status=Order.Status.DELIVERED,
        payment_status=Order.PaymentStatus.UNPAID,
    ).order_by("delivered_at")

    dish_stats = get_dish_queue_stats()
    return render(
        request,
        "orders/waiter_dashboard.html",
        {
            "orders": orders,
            "unpaid_delivered": unpaid_delivered,
            "dish_stats": dish_stats,
            "my_escalations": my_escalations,
        },
    )


@role_required(*WAITER_ROLES)
@require_POST
def order_mark_delivered(
    request: AuthenticatedHttpRequest, order_id: int
) -> HttpResponse:
    """Waiter marks a READY order as delivered to visitor."""
    order = get_object_or_404(Order, pk=order_id, waiter=request.user)
    try:
        deliver_order(order, waiter=request.user)
        messages.success(request, f"Замовлення #{order_id} передано відвідувачу.")
    except ValueError as e:
        messages.error(request, str(e))

    return redirect(f"{reverse('waiter:order_list')}?tab=my")


@role_required(*WAITER_ROLES)
@require_POST
def order_confirm_payment(
    request: AuthenticatedHttpRequest, order_id: int
) -> HttpResponse:
    """Waiter confirms cash payment for an order."""
    order = get_object_or_404(Order, pk=order_id, waiter=request.user)
    try:
        confirm_cash_payment(order, waiter=request.user)
        messages.success(
            request, f"Оплату замовлення #{order_id} підтверджено (готівка)."
        )
    except ValueError as e:
        messages.error(request, str(e))

    return redirect(f"{reverse('waiter:order_list')}?tab=my")


@role_required(*WAITER_ROLES)
def handoff_confirm_view(
    request: AuthenticatedHttpRequest, token: uuid.UUID
) -> HttpResponse:
    """Waiter confirms dish handoff after scanning QR.

    GET:  show handoff details (dish, cook, order).
    POST: confirm the handoff atomically.
    """
    handoff = get_object_or_404(KitchenHandoff, token=token)

    if handoff.target_waiter_id != request.user.id:
        return HttpResponse("Цей QR-код призначений іншому офіціанту.", status=403)

    if handoff.is_expired:
        return render(
            request, "orders/handoff_expired.html", {"handoff": handoff}, status=400
        )

    if handoff.is_confirmed:
        return render(
            request, "orders/handoff_already_confirmed.html", {"handoff": handoff}
        )

    if request.method == "POST":
        with transaction.atomic():
            handoff.is_confirmed = True
            handoff.confirmed_at = timezone.now()
            handoff.save(update_fields=["is_confirmed", "confirmed_at"])

        dish_title = handoff.ticket.order_item.dish.title
        messages.success(request, f"Прийом '{dish_title}' підтверджено.")

        # Notify visitor: waiter collected the dish
        push_visitor_event(
            order_id=handoff.ticket.order_item.order_id,
            event_type="dish_collecting",
            data={
                "ticket_id": handoff.ticket.pk,
                "dish": dish_title[:40],
                "waiter_label": request.user.staff_label,
            },
        )
        return redirect("waiter:order_list")

    ttl_remaining = max(
        0,
        settings.HANDOFF_TOKEN_TTL
        - int((timezone.now() - handoff.created_at).total_seconds()),
    )
    return render(
        request,
        "orders/handoff_confirm.html",
        {"handoff": handoff, "ttl_remaining": ttl_remaining},
    )


@role_required(*WAITER_ROLES)
@require_POST
def escalation_acknowledge(
    request: AuthenticatedHttpRequest, escalation_id: int
) -> HttpResponse:
    """Waiter acknowledges a visitor escalation."""
    escalation = get_object_or_404(VisitorEscalation, pk=escalation_id)
    try:
        acknowledge_escalation(escalation, request.user)
        messages.success(request, "Звернення позначено як побачене.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("waiter:order_list")


@role_required(*WAITER_ROLES)
@require_POST
def escalation_resolve(
    request: AuthenticatedHttpRequest, escalation_id: int
) -> HttpResponse:
    """Waiter resolves a visitor escalation."""
    escalation = get_object_or_404(VisitorEscalation, pk=escalation_id)
    note = request.POST.get("note", "")
    try:
        resolve_escalation(escalation, request.user, note=note)
        messages.success(request, "Звернення вирішено.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("waiter:order_list")


SENIOR_ROLES = ("senior_waiter", "manager")


@role_required(*SENIOR_ROLES)
def senior_waiter_dashboard(request: AuthenticatedHttpRequest) -> HttpResponse:
    """Senior waiter dashboard — escalated unpaid orders."""
    escalated_orders = (
        Order.objects.filter(
            status=Order.Status.DELIVERED,
            payment_status=Order.PaymentStatus.UNPAID,
            payment_escalation_level__gte=1,
        )
        .select_related("waiter", "visitor")
        .prefetch_related("items__dish")
        .order_by("delivered_at")
    )

    now = timezone.now()
    orders_with_age = [
        {
            "order": order,
            "minutes_since_delivery": (
                int((now - order.delivered_at).total_seconds() / 60)
                if order.delivered_at
                else None
            ),
            "escalation_level": order.payment_escalation_level,
        }
        for order in escalated_orders
    ]

    return render(
        request,
        "orders/senior_waiter_dashboard.html",
        {"orders_with_age": orders_with_age},
    )


@role_required(*SENIOR_ROLES)
@require_POST
def senior_confirm_payment(
    request: AuthenticatedHttpRequest, order_id: int
) -> HttpResponse:
    """Senior waiter confirms payment on behalf of assigned waiter."""
    order = get_object_or_404(
        Order,
        pk=order_id,
        payment_status=Order.PaymentStatus.UNPAID,
    )
    payment_type = request.POST.get("payment_type", "")
    try:
        confirm_payment_by_senior(order, method=payment_type)
        messages.success(request, f"Оплату замовлення #{order_id} підтверджено.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("waiter:senior_dashboard")
