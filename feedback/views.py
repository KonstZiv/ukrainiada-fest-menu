"""Feedback views — submit, public board, moderation."""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from feedback.models import GuestFeedback
from feedback.services import (
    create_feedback,
    feature_feedback,
    get_public_feedback,
    publish_feedback,
)
from orders.models import Order
from orders.services import can_access_order
from user.decorators import role_required


@require_POST
def submit_feedback(request: HttpRequest, order_id: int) -> HttpResponse:
    """Visitor submits feedback for a delivered order."""
    order = get_object_or_404(Order, pk=order_id)
    if not can_access_order(request, order):
        return render(request, "403.html", status=403)

    mood = request.POST.get("mood", "")
    msg = request.POST.get("message", "")
    visitor_name = request.POST.get("visitor_name", "")
    try:
        create_feedback(order, mood=mood, message=msg, visitor_name=visitor_name)
        messages.success(request, "Дякуємо за відгук! 🙏")
    except ValueError as e:
        messages.warning(request, str(e))

    return redirect("orders:order_detail", order_id=order_id)


def feedback_board(request: HttpRequest) -> HttpResponse:
    """Public feedback board — shows published guest feedback."""
    feedbacks = get_public_feedback(limit=50)
    return render(request, "feedback/board.html", {"feedbacks": feedbacks})


@role_required("manager")
def moderate_feedback_view(request: HttpRequest) -> HttpResponse:
    """List unpublished feedback for manager moderation."""
    pending = GuestFeedback.objects.filter(is_published=False).order_by("-created_at")
    published = GuestFeedback.objects.filter(is_published=True).order_by("-created_at")[
        :20
    ]
    return render(
        request,
        "feedback/moderate.html",
        {"pending": pending, "published": published},
    )


@role_required("manager")
@require_POST
def moderate_action(request: HttpRequest, feedback_id: int) -> HttpResponse:
    """Publish, feature, or reject feedback."""
    fb = get_object_or_404(GuestFeedback, pk=feedback_id)
    action = request.POST.get("action", "")

    if action == "publish":
        publish_feedback(fb)
        messages.success(request, "Відгук опубліковано.")
    elif action == "feature":
        feature_feedback(fb)
        messages.success(request, "Відгук виділено і опубліковано.")
    elif action == "reject":
        fb.delete()
        messages.info(request, "Відгук видалено.")

    return redirect("feedback:moderate")
