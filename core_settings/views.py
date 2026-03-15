from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from core_settings.forms import StudyForm


def form_handler(request: HttpRequest) -> HttpResponse:
    num_visits = request.session.get("num_visits", 0)
    num_visits = num_visits + 1
    request.session["num_visits"] = num_visits

    if request.method == "POST":
        print(request.POST)
        form = StudyForm(request.POST)
        if form.is_valid():
            print(form.cleaned_data)

            # роблю щось
            return HttpResponseRedirect(reverse("menu:index"))

    else:
        form = StudyForm()
        # відправити пусту форму
    return render(request, "form.html", {"form": form, "num_visits": num_visits})
