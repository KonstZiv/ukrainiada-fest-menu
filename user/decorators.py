"""Access control decorators based on user roles."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Concatenate, ParamSpec, TypeVar, cast

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from user.models import User

_P = ParamSpec("_P")
_R = TypeVar("_R", bound=HttpResponse)
_Req = TypeVar("_Req", bound=HttpRequest)


def role_required(
    *roles: str,
) -> Callable[
    [Callable[Concatenate[_Req, _P], _R]],
    Callable[Concatenate[_Req, _P], HttpResponse],
]:
    """Restrict view access to users with specific roles.

    Views decorated with this should type request as
    AuthenticatedHttpRequest for proper request.user typing.
    """

    def decorator(
        view_func: Callable[Concatenate[_Req, _P], _R],
    ) -> Callable[Concatenate[_Req, _P], HttpResponse]:
        @wraps(view_func)
        def wrapper(request: _Req, *args: _P.args, **kwargs: _P.kwargs) -> HttpResponse:
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            user = cast(User, request.user)
            if user.role not in roles:
                return HttpResponseForbidden("Доступ заборонено")
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def verified_channel_required[**P, Req: HttpRequest](
    view_func: Callable[Concatenate[Req, P], HttpResponse],
) -> Callable[Concatenate[Req, P], HttpResponse]:
    """Require at least one verified communication channel."""

    @wraps(view_func)
    def wrapper(request: Req, *args: P.args, **kwargs: P.kwargs) -> HttpResponse:
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        user = cast(User, request.user)
        if not user.channels.filter(is_verified=True).exists():
            messages.warning(
                request,
                _("Для цієї дії потрібен верифікований канал комунікації."),
            )
            return redirect("user:channels")
        return view_func(request, *args, **kwargs)

    return wrapper
