"""Kitchen-facing views: dashboard and ticket actions."""

from __future__ import annotations

import datetime
import io
from itertools import groupby
from typing import Any

import qrcode  # type: ignore[import-untyped]
from django.contrib import messages
from django.db.models import Count, Max, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core_settings.types import AuthenticatedHttpRequest
from kitchen.helpers import enrich_tickets, group_by_order
from kitchen.models import KitchenTicket
from kitchen.services import (
    create_handoff,
    get_pending_tickets_for_user,
    manual_handoff,
    mark_ticket_done,
    take_ticket,
)
from user.constants import KITCHEN_ROLES, KITCHEN_SUPERVISOR_ROLES
from user.decorators import role_required
from user.models import User

SUPERVISOR_ROLES = KITCHEN_SUPERVISOR_ROLES


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@role_required(*KITCHEN_ROLES)
def kitchen_dashboard(request: AuthenticatedHttpRequest) -> HttpResponse:
    """Kitchen dashboard — tabs: queue, in_progress, done, team."""
    user = request.user
    now = timezone.now()
    tab = request.GET.get("tab", "queue")
    is_supervisor = user.role in SUPERVISOR_ROLES

    # --- Pending (queue) ---
    if user.role == user.Role.KITCHEN:
        pending_qs = get_pending_tickets_for_user(user.id).select_related(
            "order_item__order__waiter"
        )
    else:
        pending_qs = KitchenTicket.objects.filter(
            status=KitchenTicket.Status.PENDING
        ).select_related("order_item__dish", "order_item__order__waiter")

    pending_enriched = enrich_tickets(pending_qs, now)
    pending_groups = group_by_order(pending_enriched)

    # --- Escalated (supervisor/manager only) ---
    escalated_groups: list[dict[str, Any]] = []
    escalated_count = 0
    if is_supervisor:
        level = (
            KitchenTicket.EscalationLevel.SUPERVISOR
            if user.role == user.Role.KITCHEN_SUPERVISOR
            else KitchenTicket.EscalationLevel.MANAGER
        )
        escalated_qs = KitchenTicket.objects.filter(
            status=KitchenTicket.Status.PENDING,
            escalation_level__gte=level,
        ).select_related("order_item__dish", "order_item__order__waiter")
        escalated_enriched = enrich_tickets(escalated_qs, now)
        escalated_groups = group_by_order(escalated_enriched)
        escalated_count = len(escalated_enriched)

    # --- Taken (in_progress) ---
    taken_qs = KitchenTicket.objects.filter(
        status=KitchenTicket.Status.TAKEN,
        assigned_to=user,
    ).select_related("order_item__dish", "order_item__order__waiter")
    taken_enriched = enrich_tickets(taken_qs, now)
    taken_groups = group_by_order(taken_enriched)

    # --- Done (still on kitchen, not handed to waiter yet) ---
    done_qs = (
        KitchenTicket.objects.filter(
            status=KitchenTicket.Status.DONE,
            assigned_to=user,
            handed_off_at__isnull=True,
        )
        .select_related("order_item__dish", "order_item__order__waiter")
        .order_by("-done_at")
    )
    done_enriched = enrich_tickets(done_qs, now)
    done_groups = group_by_order(done_enriched)

    # --- Team data (supervisor/manager, only when tab == "team") ---
    team_data: list[dict[str, Any]] = []
    team_stats_details: list[dict[str, Any]] = []
    team_stats_totals: dict[str, Any] = {}
    if is_supervisor and tab == "team":
        from orders.stats import period_range

        today = period_range("today")[0]

        from orders.stats import kitchen_stats, period_range

        period = request.GET.get("period", "today")
        if period not in ("today", "yesterday", "week"):
            period = "today"
        stats_since, stats_until = period_range(period)
        team_stats_details, team_stats_totals = kitchen_stats(stats_since, stats_until)
        kitchen_users = (
            User.objects.filter(
                role__in=[User.Role.KITCHEN, User.Role.KITCHEN_SUPERVISOR],
            )
            .annotate(
                pending_count=Count(
                    "kitchen_assignments__dish__order_items__kitchen_tickets",
                    filter=Q(
                        kitchen_assignments__dish__order_items__kitchen_tickets__status=KitchenTicket.Status.PENDING,
                    ),
                ),
                taken_count=Count(
                    "kitchen_tickets",
                    filter=Q(kitchen_tickets__status=KitchenTicket.Status.TAKEN),
                ),
                done_count=Count(
                    "kitchen_tickets",
                    filter=Q(
                        kitchen_tickets__status=KitchenTicket.Status.DONE,
                        kitchen_tickets__done_at__gte=today,
                    ),
                ),
                escalated_count=Count(
                    "kitchen_assignments__dish__order_items__kitchen_tickets",
                    filter=Q(
                        kitchen_assignments__dish__order_items__kitchen_tickets__status=KitchenTicket.Status.PENDING,
                        kitchen_assignments__dish__order_items__kitchen_tickets__escalation_level__gte=KitchenTicket.EscalationLevel.SUPERVISOR,
                    ),
                ),
            )
            .order_by("first_name", "email")
        )
        for cook in kitchen_users:
            team_data.append(
                {
                    "cook": cook,
                    "pending": cook.pending_count,
                    "taken": cook.taken_count,
                    "done": cook.done_count,
                    "escalated": cook.escalated_count,
                }
            )

    # Last escalation id — for polling comparison
    last_esc = KitchenTicket.objects.filter(
        escalation_level__gte=KitchenTicket.EscalationLevel.SUPERVISOR,
    ).aggregate(last_id=Max("id"))
    last_escalation_id: int = last_esc["last_id"] or 0

    return render(
        request,
        "kitchen/dashboard.html",
        {
            "active_tab": tab,
            "pending_groups": pending_groups,
            "taken_groups": taken_groups,
            "done_groups": done_groups,
            "escalated_groups": escalated_groups,
            "pending_count": len(pending_enriched),
            "taken_count": len(taken_enriched),
            "done_count": len(done_enriched),
            "escalated_count": escalated_count,
            "is_supervisor": is_supervisor,
            "team_data": team_data,
            "team_stats_details": team_stats_details,
            "team_stats_totals": team_stats_totals,
            "last_escalation_id": last_escalation_id,
        },
    )


# ---------------------------------------------------------------------------
# Polling endpoint (temporary — remove when SSE/ASGI is deployed)
# ---------------------------------------------------------------------------


@role_required(*KITCHEN_ROLES)
def kitchen_poll_data(request: AuthenticatedHttpRequest) -> HttpResponse:
    """Return kitchen dashboard counts as JSON for polling.

    Optimized: single aggregate query for taken/done counts,
    separate query for pending (role-dependent filter).
    """
    user = request.user

    # Pending count depends on role (regular cook sees only assigned dishes)
    if user.role == user.Role.KITCHEN:
        pending_count = get_pending_tickets_for_user(user.id).count()
    else:
        pending_count = KitchenTicket.objects.filter(
            status=KitchenTicket.Status.PENDING
        ).count()

    # Single aggregate for taken + done + escalated + last_esc_id
    is_supervisor = user.role in SUPERVISOR_ROLES
    esc_level = (
        KitchenTicket.EscalationLevel.SUPERVISOR
        if user.role == user.Role.KITCHEN_SUPERVISOR
        else KitchenTicket.EscalationLevel.MANAGER
    )
    counts = KitchenTicket.objects.aggregate(
        taken_count=Count(
            "id",
            filter=Q(status=KitchenTicket.Status.TAKEN, assigned_to=user),
        ),
        done_count=Count(
            "id",
            filter=Q(
                status=KitchenTicket.Status.DONE,
                assigned_to=user,
                handed_off_at__isnull=True,
            ),
        ),
        escalated_count=Count(
            "id",
            filter=Q(
                status=KitchenTicket.Status.PENDING,
                escalation_level__gte=esc_level,
            ),
        ),
        last_esc_id=Max(
            "id",
            filter=Q(
                escalation_level__gte=KitchenTicket.EscalationLevel.SUPERVISOR,
            ),
        ),
    )
    taken_count: int = counts["taken_count"]
    done_count: int = counts["done_count"]
    escalated_count: int = counts["escalated_count"] if is_supervisor else 0
    last_escalation_id: int = counts["last_esc_id"] or 0

    # Compare with client-side known state
    client_last = int(request.GET.get("last_esc", "0") or "0")
    has_new_escalation = last_escalation_id > client_last

    return JsonResponse(
        {
            "pending_count": pending_count,
            "taken_count": taken_count,
            "done_count": done_count,
            "escalated_count": escalated_count,
            "has_new_escalation": has_new_escalation,
            "last_escalation_id": last_escalation_id,
        }
    )


# ---------------------------------------------------------------------------
# Ticket actions
# ---------------------------------------------------------------------------


@role_required(*KITCHEN_ROLES)
@require_POST
def ticket_take(request: AuthenticatedHttpRequest, ticket_id: int) -> HttpResponse:
    """Kitchen staff takes a pending ticket."""
    ticket = get_object_or_404(KitchenTicket, pk=ticket_id)
    try:
        take_ticket(ticket, kitchen_user=request.user)
    except ValueError as e:
        messages.error(request, str(e))
    tab = request.POST.get("tab", "queue")
    return redirect(f"{reverse('kitchen:dashboard')}?tab={tab}")


@role_required(*KITCHEN_ROLES)
@require_POST
def ticket_done(request: AuthenticatedHttpRequest, ticket_id: int) -> HttpResponse:
    """Kitchen staff marks a ticket as done (auto-takes if PENDING)."""
    ticket = get_object_or_404(KitchenTicket, pk=ticket_id)
    try:
        ticket, skipped = mark_ticket_done(ticket, kitchen_user=request.user)
        if skipped:
            dish_title = ticket.order_item.dish.title
            messages.warning(
                request,
                f"'{dish_title}' — пропущено: {', '.join(skipped)}",
            )
    except ValueError as e:
        messages.error(request, str(e))
    tab = request.POST.get("tab", "in_progress")
    return redirect(f"{reverse('kitchen:dashboard')}?tab={tab}")


@role_required(*KITCHEN_ROLES)
def generate_handoff_qr(
    request: AuthenticatedHttpRequest, ticket_id: int
) -> HttpResponse:
    """Generate a QR code for dish handoff to a specific waiter.

    GET:  show waiter selection form.
    POST: create handoff token and return QR code as PNG.
    """
    ticket = get_object_or_404(
        KitchenTicket,
        pk=ticket_id,
        assigned_to=request.user,
        status=KitchenTicket.Status.DONE,
    )

    if request.method == "POST":
        waiter_id = request.POST.get("waiter_id", "")
        try:
            target_waiter = User.objects.get(
                pk=int(waiter_id),
                role__in=[User.Role.WAITER, User.Role.SENIOR_WAITER],
            )
        except User.DoesNotExist, ValueError:
            messages.error(
                request,
                "Обраний офіціант не знайдений або не має відповідної ролі.",
            )
            return redirect(request.path)

        handoff = create_handoff(ticket, target_waiter=target_waiter)

        confirm_path = reverse("waiter:handoff_confirm", args=[handoff.token])
        scan_url = request.build_absolute_uri(confirm_path)

        qr = qrcode.QRCode(version=1, box_size=8, border=4)
        qr.add_data(scan_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return HttpResponse(buffer.getvalue(), content_type="image/png")

    # GET — waiter selection form
    waiters = User.objects.filter(
        role__in=[User.Role.WAITER, User.Role.SENIOR_WAITER],
    )
    return render(
        request,
        "kitchen/handoff_select_waiter.html",
        {"ticket": ticket, "waiters": waiters},
    )


@role_required(*KITCHEN_ROLES)
@require_POST
def ticket_manual_handoff(
    request: AuthenticatedHttpRequest, ticket_id: int
) -> HttpResponse:
    """Cook manually confirms dish handoff (fallback without QR)."""
    ticket = get_object_or_404(
        KitchenTicket,
        pk=ticket_id,
        assigned_to=request.user,
        status=KitchenTicket.Status.DONE,
    )
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    try:
        manual_handoff(ticket, kitchen_user=request.user)
        dish_title = ticket.order_item.dish.title
        if is_ajax:
            return JsonResponse({"ok": True, "dish": dish_title})
    except ValueError as e:
        if is_ajax:
            return JsonResponse({"ok": False, "error": str(e)}, status=400)
        messages.error(request, str(e))
    tab = request.POST.get("tab", "done")
    return redirect(f"{reverse('kitchen:dashboard')}?tab={tab}")
