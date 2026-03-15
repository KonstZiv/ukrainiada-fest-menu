"""Timeout helper functions returning timedelta objects."""

from datetime import timedelta

from django.conf import settings


def kitchen_timeout() -> timedelta:
    """Return kitchen processing timeout as timedelta."""
    return timedelta(minutes=settings.KITCHEN_TIMEOUT)


def manager_timeout() -> timedelta:
    """Return cumulative manager escalation timeout (kitchen + manager)."""
    return timedelta(minutes=settings.KITCHEN_TIMEOUT + settings.MANAGER_TIMEOUT)


def pay_timeout() -> timedelta:
    """Return payment timeout as timedelta."""
    return timedelta(minutes=settings.PAY_TIMEOUT)
