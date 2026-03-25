from typing import cast

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from user.forms import ProfileEditForm, SignUpForm
from user.models import CommunicationChannel, User


def get_profile(request: HttpRequest) -> HttpResponse:
    context: dict[str, object] = {}
    if request.user.is_authenticated:
        context["channels"] = request.user.channels.all()  # type: ignore[union-attr]
    return render(request, "user/profile.html", context)


@login_required
def edit_profile(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect(reverse("user:profile"))
    else:
        form = ProfileEditForm(instance=request.user)
    return render(request, "user/profile_edit.html", {"form": form})


def sign_up(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            CommunicationChannel.objects.create(
                user=user,
                channel_type=CommunicationChannel.ChannelType.EMAIL,
                address=user.email,
                is_verified=True,
                priority=0,
            )
            login(request, user)
            return redirect(reverse("menu:index"))
    else:
        form = SignUpForm()
    return render(request, "user/sign_up.html", {"form": form})


@login_required
def manage_channels(request: HttpRequest) -> HttpResponse:
    """List and manage communication channels."""
    user = cast(User, request.user)
    channels = user.channels.all()

    if request.method == "POST":
        action = request.POST.get("action")
        channel_id = request.POST.get("channel_id")

        if action == "priority_up" and channel_id:
            _swap_priority(user, int(channel_id), direction=-1)
        elif action == "priority_down" and channel_id:
            _swap_priority(user, int(channel_id), direction=1)
        elif action == "delete" and channel_id:
            ch = channels.filter(id=channel_id).first()
            # Don't delete last verified channel.
            if ch and channels.filter(is_verified=True).count() > 1:
                ch.delete()

        return redirect(reverse("user:channels"))

    return render(
        request,
        "user/channels.html",
        {"channels": channels, "show_search": False},
    )


def _swap_priority(user: User, channel_id: int, direction: int) -> None:
    """Swap priority of a channel with its neighbor."""
    channels = list(CommunicationChannel.objects.filter(user=user).order_by("priority"))
    idx = next((i for i, c in enumerate(channels) if c.id == channel_id), None)
    if idx is None:
        return
    swap_idx = idx + direction
    if 0 <= swap_idx < len(channels):
        channels[idx].priority, channels[swap_idx].priority = (
            channels[swap_idx].priority,
            channels[idx].priority,
        )
        channels[idx].save(update_fields=["priority"])
        channels[swap_idx].save(update_fields=["priority"])
