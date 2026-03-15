"""Access control decorators based on user roles."""

from __future__ import annotations

from functools import wraps
from typing import Any

from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden


def role_required(
    *roles: str,
) -> Any:
    """Restrict view access to users with specific roles.

    Usage:
        @role_required("waiter", "senior_waiter", "manager")
        def my_view(request): ...
    """

    def decorator(view_func: Any) -> Any:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.role not in roles:  # type: ignore[union-attr]
                return HttpResponseForbidden("Доступ заборонено")
            return view_func(request, *args, **kwargs)  # type: ignore[no-any-return]

        return wrapper

    return decorator
