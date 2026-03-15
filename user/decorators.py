"""Access control decorators based on user roles."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Concatenate, ParamSpec, TypeVar

from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden

_P = ParamSpec("_P")
_R = TypeVar("_R", bound=HttpResponse)


def role_required(
    *roles: str,
) -> Callable[
    [Callable[Concatenate[HttpRequest, _P], _R]],
    Callable[Concatenate[HttpRequest, _P], HttpResponse],
]:
    """Restrict view access to users with specific roles.

    Usage:
        @role_required("waiter", "senior_waiter", "manager")
        def my_view(request): ...
    """

    def decorator(
        view_func: Callable[Concatenate[HttpRequest, _P], _R],
    ) -> Callable[Concatenate[HttpRequest, _P], HttpResponse]:
        @wraps(view_func)
        def wrapper(
            request: HttpRequest, *args: _P.args, **kwargs: _P.kwargs
        ) -> HttpResponse:
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.role not in roles:  # type: ignore[union-attr]
                return HttpResponseForbidden("Доступ заборонено")
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
