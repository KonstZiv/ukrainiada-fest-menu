"""Waiter-facing views: order list, scan, approve, dashboard, deliver, senior."""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.db import models, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core_settings.types import AuthenticatedHttpRequest
from kitchen.models import KitchenHandoff
from orders.helpers import enrich_orders
from kitchen.stats import get_dish_queue_stats
from notifications.events import push_visitor_event
from orders.escalation_services import acknowledge_escalation, resolve_escalation
from orders.models import Order, VisitorEscalation
from orders.services import (
    accept_order,
    approve_order,
    cancel_order,
    confirm_cash_payment,
    confirm_payment_by_senior,
    deliver_order,
    deliver_ticket,
    update_order_items,
    verify_order,
)
from user.constants import SENIOR_WAITER_ROLES, WAITER_ROLES
from user.decorators import role_required

SENIOR_ROLES = SENIOR_WAITER_ROLES


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
            "items__kitchen_tickets",
            "items__kitchen_tickets__assigned_to",
        )
        .order_by("created_at")
    )

    now = timezone.now()
    pickup_warn = settings.DISH_PICKUP_WARN
    pickup_critical = settings.DISH_PICKUP_CRITICAL
    my_orders_enriched, my_ready_count = enrich_orders(
        my_orders_qs, now, pickup_warn, pickup_critical
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

    # Team tab — only for senior/manager
    is_senior = request.user.role in SENIOR_ROLES
    team_data: list[dict] = []
    team_stats_details: list[dict] = []
    team_stats_totals: dict = {}
    period = ""
    date_from = ""
    date_to = ""
    if is_senior and tab == "team":
        from itertools import groupby

        from orders.stats import resolve_period, waiter_stats

        period, stats_since, stats_until, date_from, date_to = resolve_period(
            request.GET.get("period", "today"),
            request.GET.get("date_from", ""),
            request.GET.get("date_to", ""),
        )
        team_stats_details, team_stats_totals = waiter_stats(stats_since, stats_until)

        all_active = (
            Order.objects.filter(
                status__in=[
                    Order.Status.ACCEPTED,
                    Order.Status.VERIFIED,
                    Order.Status.IN_PROGRESS,
                    Order.Status.READY,
                ],
                waiter__isnull=False,
            )
            .select_related("waiter")
            .prefetch_related(
                "items__dish",
                "items__kitchen_tickets",
                "items__kitchen_tickets__assigned_to",
            )
            .order_by("waiter_id", "created_at")
        )
        all_unpaid = (
            Order.objects.filter(
                status=Order.Status.DELIVERED,
                payment_status=Order.PaymentStatus.UNPAID,
                waiter__isnull=False,
            )
            .select_related("waiter")
            .prefetch_related("items__dish")
            .order_by("waiter_id")
        )
        all_cash = (
            Order.objects.filter(
                payment_status=Order.PaymentStatus.PAID,
                payment_method=Order.PaymentMethod.CASH,
                waiter__isnull=False,
            )
            .select_related("waiter")
            .prefetch_related("items__dish")
        )

        # Group by waiter
        unpaid_by_waiter: dict[int, list[Order]] = {}
        for o in all_unpaid:
            if o.waiter_id is not None:
                unpaid_by_waiter.setdefault(o.waiter_id, []).append(o)

        cash_by_waiter: dict[int, Decimal] = {}
        for o in all_cash:
            if o.waiter_id is not None:
                cash_by_waiter[o.waiter_id] = (
                    cash_by_waiter.get(o.waiter_id, Decimal("0")) + o.total_price
                )

        for waiter_id, group in groupby(all_active, key=lambda o: o.waiter_id):
            orders_list = list(group)
            if not orders_list or waiter_id is None:
                continue
            waiter = orders_list[0].waiter
            enriched, _ = enrich_orders(orders_list, now, pickup_warn, pickup_critical)
            overdue_count = sum(1 for e in enriched if e["has_overdue"])
            team_data.append(
                {
                    "waiter": waiter,
                    "orders": enriched,
                    "order_count": len(enriched),
                    "overdue_count": overdue_count,
                    "unpaid_orders": unpaid_by_waiter.get(waiter_id, []),
                    "unpaid_count": len(unpaid_by_waiter.get(waiter_id, [])),
                    "cash_total": cash_by_waiter.get(waiter_id, Decimal("0")),
                }
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
            "is_senior": is_senior,
            "team_data": team_data,
            "team_stats_details": team_stats_details,
            "team_stats_totals": team_stats_totals,
            "current_period": period,
            "date_from": date_from,
            "date_to": date_to,
            "extra_params_list": [("tab", "team")],
        },
    )


@role_required(*WAITER_ROLES)
def waiter_poll_data(request: AuthenticatedHttpRequest) -> HttpResponse:
    """Return waiter board counts as JSON for polling.

    Temporary — remove when SSE/ASGI is deployed.
    """
    counts = Order.objects.aggregate(
        new_count=models.Count("id", filter=models.Q(status=Order.Status.SUBMITTED)),
        my_count=models.Count(
            "id",
            filter=models.Q(
                waiter=request.user,
                status__in=[
                    Order.Status.ACCEPTED,
                    Order.Status.VERIFIED,
                    Order.Status.IN_PROGRESS,
                    Order.Status.READY,
                ],
            ),
        ),
        unpaid_count=models.Count(
            "id",
            filter=models.Q(
                waiter=request.user,
                status=Order.Status.DELIVERED,
                payment_status=Order.PaymentStatus.UNPAID,
            ),
        ),
    )
    return JsonResponse(counts)


@role_required(*WAITER_ROLES)
def order_scan(request: AuthenticatedHttpRequest, order_id: int) -> HttpResponse:
    """Waiter scans QR — redirects to order detail for approval."""
    from orders.services import can_edit_order

    order = get_object_or_404(Order, pk=order_id)
    can_edit = can_edit_order(order, request)
    return render(
        request,
        "orders/waiter_order_detail.html",
        {"order": order, "can_edit": can_edit},
    )


@role_required(*WAITER_ROLES)
@require_POST
def order_accept(request: AuthenticatedHttpRequest, order_id: int) -> HttpResponse:
    """Waiter takes (accepts) a SUBMITTED order."""
    order = get_object_or_404(Order, pk=order_id)
    try:
        accept_order(order, request.user)
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
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("waiter:order_scan", order_id=order.id)


@role_required(*WAITER_ROLES)
def waiter_dashboard(request: AuthenticatedHttpRequest) -> HttpResponse:
    """Legacy dashboard — redirect to new order board."""
    return redirect(f"{reverse('waiter:order_list')}?tab=my")


@role_required(*WAITER_ROLES)
@require_POST
def order_mark_delivered(
    request: AuthenticatedHttpRequest, order_id: int
) -> HttpResponse:
    """Waiter marks order as delivered to visitor (soft flow: auto-completes if needed)."""
    order = get_object_or_404(Order, pk=order_id, waiter=request.user)
    try:
        order, skipped = deliver_order(order, waiter=request.user)
        if skipped:
            messages.warning(
                request,
                f"#{order_id} — пропущені кроки: {', '.join(skipped)}",
            )
    except ValueError as e:
        messages.error(request, str(e))

    return redirect(f"{reverse('waiter:order_list')}?tab=my")


@role_required(*WAITER_ROLES)
@require_POST
def ticket_mark_delivered(
    request: AuthenticatedHttpRequest, ticket_id: int
) -> HttpResponse:
    """Waiter marks a single portion as delivered to visitor."""
    from kitchen.models import KitchenTicket

    ticket = get_object_or_404(KitchenTicket, pk=ticket_id)
    order_id = ticket.order_item.order_id
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    try:
        deliver_ticket(ticket, waiter=request.user)
        dish_title = ticket.order_item.dish.title
        if is_ajax:
            all_done = not KitchenTicket.objects.filter(
                order_item__order_id=order_id, is_delivered=False
            ).exists()
            return JsonResponse(
                {
                    "ok": True,
                    "dish": dish_title,
                    "all_delivered": all_done,
                }
            )
    except ValueError as e:
        if is_ajax:
            return JsonResponse({"ok": False, "error": str(e)}, status=400)
        messages.error(request, str(e))

    return redirect(f"{reverse('waiter:order_list')}?tab=my&open={order_id}")


@role_required(*WAITER_ROLES)
@require_POST
def order_confirm_payment(
    request: AuthenticatedHttpRequest, order_id: int
) -> HttpResponse:
    """Waiter confirms cash payment (soft flow: auto-delivers if needed)."""
    order = get_object_or_404(Order, pk=order_id, waiter=request.user)
    try:
        order, skipped = confirm_cash_payment(order, waiter=request.user)
        if skipped:
            messages.warning(
                request,
                f"#{order_id} оплата — пропущені кроки: {', '.join(skipped)}",
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


# ---------------------------------------------------------------------------
# Z5: Edit / Cancel orders (waiter AJAX)
# ---------------------------------------------------------------------------


@role_required(*WAITER_ROLES)
@require_POST
def waiter_edit_items(request: AuthenticatedHttpRequest, order_id: int) -> HttpResponse:
    """Waiter edits item quantities (AJAX, JSON body)."""
    import json

    order = get_object_or_404(
        Order.objects.prefetch_related("items__dish"),
        pk=order_id,
        waiter=request.user,
    )

    try:
        body = json.loads(request.body)
        changes: dict[int, int] = {
            int(k): int(v) for k, v in body.get("items", {}).items()
        }
    except json.JSONDecodeError, ValueError, TypeError:
        return JsonResponse({"ok": False, "error": "Invalid data"}, status=400)

    try:
        order = update_order_items(order, changes, request)
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    items_data = [
        {
            "id": item.id,
            "dish_title": item.dish.title,
            "quantity": item.quantity,
            "subtotal": str(item.subtotal),
        }
        for item in order.items.select_related("dish")
    ]
    return JsonResponse(
        {
            "ok": True,
            "status": order.status,
            "total_price": str(order.total_price),
            "items": items_data,
        }
    )


@role_required(*WAITER_ROLES)
@require_POST
def waiter_cancel_order(
    request: AuthenticatedHttpRequest, order_id: int
) -> HttpResponse:
    """Waiter cancels order (AJAX)."""
    order = get_object_or_404(Order, pk=order_id, waiter=request.user)

    try:
        cancel_order(order, request)
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    return JsonResponse({"ok": True, "status": "cancelled"})
