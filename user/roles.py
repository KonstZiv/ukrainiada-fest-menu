"""Role-checking helpers for the restaurant system."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from user.models import User


def is_kitchen_staff(user: User) -> bool:
    """Return True if user has a kitchen role."""
    return user.role in (user.Role.KITCHEN, user.Role.KITCHEN_SUPERVISOR)


def is_waiter_staff(user: User) -> bool:
    """Return True if user has a waiter role."""
    return user.role in (user.Role.WAITER, user.Role.SENIOR_WAITER)


def is_management(user: User) -> bool:
    """Return True if user is a manager."""
    return user.role == user.Role.MANAGER
