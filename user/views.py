from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from user.forms import ProfileEditForm, SignUpForm


def get_profile(request: HttpRequest) -> HttpResponse:
    return render(request, "user/profile.html")


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
            login(request, user)
            return redirect(reverse("menu:index"))
    else:
        form = SignUpForm()
    return render(request, "user/sign_up.html", {"form": form})
