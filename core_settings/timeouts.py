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


def accept_timeout() -> timedelta:
    """Return order acceptance timeout as timedelta."""
    return timedelta(minutes=settings.ACCEPT_TIMEOUT)


def verify_timeout() -> timedelta:
    """Return order verification timeout as timedelta."""
    return timedelta(minutes=settings.VERIFY_TIMEOUT)


def cooking_timeout() -> timedelta:
    """Return cooking timeout as timedelta."""
    return timedelta(minutes=settings.COOKING_TIMEOUT)


def handoff_timeout() -> timedelta:
    """Return dish handoff timeout as timedelta."""
    return timedelta(minutes=settings.HANDOFF_TIMEOUT)


def senior_response_timeout() -> timedelta:
    """Return senior response timeout as timedelta."""
    return timedelta(minutes=settings.SENIOR_RESPONSE_TIMEOUT)
