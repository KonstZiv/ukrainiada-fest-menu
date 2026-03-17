"""SSE channel name helpers.

Channels:
    kitchen-{user_id}  — for kitchen and kitchen_supervisor roles
    waiter-{user_id}   — for waiter and senior_waiter roles
    manager            — single global channel for managers
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from user.models import User


def kitchen_channel(user_id: int) -> str:
    """Return kitchen channel name for a given user."""
    return f"kitchen-{user_id}"


def waiter_channel(user_id: int) -> str:
    """Return waiter channel name for a given user."""
    return f"waiter-{user_id}"


def manager_channel() -> str:
    """Return the global manager channel name."""
    return "manager"


def visitor_order_channel(order_id: int) -> str:
    """Return visitor channel for a specific order."""
    return f"visitor-order-{order_id}"


def channels_for_user(user: User) -> list[str]:
    """Return list of SSE channels the user should subscribe to."""
    from user.models import User as UserModel

    role = user.role
    if role in (UserModel.Role.KITCHEN, UserModel.Role.KITCHEN_SUPERVISOR):
        return [kitchen_channel(user.id), "kitchen-broadcast"]
    if role in (UserModel.Role.WAITER, UserModel.Role.SENIOR_WAITER):
        return [waiter_channel(user.id)]
    if role == UserModel.Role.MANAGER:
        return [manager_channel(), "kitchen-broadcast"]
    return []
