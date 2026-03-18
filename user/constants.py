"""Centralized role group constants for @role_required decorators."""

KITCHEN_ROLES: tuple[str, ...] = ("kitchen", "kitchen_supervisor", "manager")
KITCHEN_SUPERVISOR_ROLES: tuple[str, ...] = ("kitchen_supervisor", "manager")
WAITER_ROLES: tuple[str, ...] = ("waiter", "senior_waiter", "manager")
SENIOR_WAITER_ROLES: tuple[str, ...] = ("senior_waiter", "manager")
