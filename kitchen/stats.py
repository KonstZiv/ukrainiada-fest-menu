"""Kitchen throughput statistics for waiter dashboard."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from kitchen.models import KitchenTicket


def get_dish_queue_stats() -> dict[int, dict[str, int]]:
    """Return per-dish queue stats in a single SQL query.

    Returns:
        {dish_id: {"pending": N, "done_recently": M}}

    "done_recently" — count of dishes completed within the last
    SPEED_INTERVAL_KITCHEN minutes (from settings).

    """
    window_start = timezone.now() - timedelta(minutes=settings.SPEED_INTERVAL_KITCHEN)

    stats_qs = KitchenTicket.objects.values("order_item__dish_id").annotate(
        pending=Count("id", filter=Q(status=KitchenTicket.Status.PENDING)),
        done_recently=Count(
            "id",
            filter=Q(
                status=KitchenTicket.Status.DONE,
                done_at__gte=window_start,
            ),
        ),
    )

    return {
        row["order_item__dish_id"]: {
            "pending": row["pending"],
            "done_recently": row["done_recently"],
        }
        for row in stats_qs
    }
