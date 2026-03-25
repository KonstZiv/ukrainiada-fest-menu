"""Views for news articles — public list/detail and editor CRUD."""

from __future__ import annotations

from typing import Any, cast

from django.db import transaction
from django.db.models import Prefetch, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.views import generic

from news.forms import ArticleForm, ArticleImageFormSet, ArticleMainImageForm
from news.models import Article, ArticleMainImage
from user.decorators import role_required
from user.models import User

_EDITOR_ROLES = ("editor", "manager")


# ---------------------------------------------------------------------------
# Public views
# ---------------------------------------------------------------------------


def article_list(request: HttpRequest) -> HttpResponse:
    """Public list of published articles."""
    articles = (
        Article.objects.filter(status=Article.Status.PUBLISHED)
        .select_related("main_image", "topic", "author")
        .prefetch_related("tags")
    )
    return render(
        request,
        "news/article_list.html",
        {"articles": articles, "show_search": False},
    )


def article_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Public article detail with full content."""
    qs: QuerySet[Article] = Article.objects.select_related(
        "main_image", "topic", "author"
    ).prefetch_related("tags", "images")

    # Editors/managers see all statuses; visitors only published.
    user = request.user
    if user.is_authenticated and cast(User, user).role in _EDITOR_ROLES:
        article = get_object_or_404(qs, pk=pk)
    else:
        article = get_object_or_404(qs, pk=pk, status=Article.Status.PUBLISHED)

    return render(
        request,
        "news/article_detail.html",
        {"article": article, "show_search": False},
    )


# ---------------------------------------------------------------------------
# Editor CRUD
# ---------------------------------------------------------------------------


class ArticleCreateView(generic.CreateView):  # type: ignore[type-arg]
    model = Article
    form_class = ArticleForm
    template_name = "news/article_form.html"
    success_url = reverse_lazy("news:article_list")

    @classmethod
    def as_view(cls, **kwargs: Any) -> Any:
        view = super().as_view(**kwargs)
        return role_required(*_EDITOR_ROLES)(view)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx["image_form"] = ArticleMainImageForm(
                self.request.POST, self.request.FILES, prefix="main_image"
            )
            ctx["image_formset"] = ArticleImageFormSet(
                self.request.POST, self.request.FILES, prefix="images"
            )
        else:
            ctx["image_form"] = ArticleMainImageForm(prefix="main_image")
            ctx["image_formset"] = ArticleImageFormSet(prefix="images")
        ctx["show_search"] = False
        return ctx

    def form_valid(self, form: ArticleForm) -> HttpResponse:
        ctx = self.get_context_data()
        image_form: ArticleMainImageForm = ctx["image_form"]
        image_formset: ArticleImageFormSet = ctx["image_formset"]

        has_image = bool(self.request.FILES.get("main_image-image"))
        if not has_image:
            image_form.add_error("image", "Обов'язкове поле")

        if not image_form.is_valid() or not image_formset.is_valid():
            return self.render_to_response(ctx)

        with transaction.atomic():
            form.instance.author = cast(User, self.request.user)
            article = form.save()

            main_img: ArticleMainImage = image_form.save(commit=False)
            main_img.article = article
            main_img.save()

            image_formset.instance = article
            image_formset.save()

        return super().form_valid(form)


class ArticleUpdateView(generic.UpdateView):  # type: ignore[type-arg]
    model = Article
    form_class = ArticleForm
    template_name = "news/article_form.html"
    success_url = reverse_lazy("news:article_list")

    @classmethod
    def as_view(cls, **kwargs: Any) -> Any:
        view = super().as_view(**kwargs)
        return role_required(*_EDITOR_ROLES)(view)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        article = self.object
        if self.request.POST:
            ctx["image_form"] = ArticleMainImageForm(
                self.request.POST,
                self.request.FILES,
                prefix="main_image",
                instance=getattr(article, "main_image", None),
            )
            ctx["image_formset"] = ArticleImageFormSet(
                self.request.POST,
                self.request.FILES,
                prefix="images",
                instance=article,
            )
        else:
            ctx["image_form"] = ArticleMainImageForm(
                prefix="main_image",
                instance=getattr(article, "main_image", None),
            )
            ctx["image_formset"] = ArticleImageFormSet(
                prefix="images", instance=article
            )
        ctx["show_search"] = False
        return ctx

    def form_valid(self, form: ArticleForm) -> HttpResponse:
        ctx = self.get_context_data()
        image_form: ArticleMainImageForm = ctx["image_form"]
        image_formset: ArticleImageFormSet = ctx["image_formset"]

        if not image_form.is_valid() or not image_formset.is_valid():
            return self.render_to_response(ctx)

        with transaction.atomic():
            article = form.save()

            if image_form.has_changed():
                main_img: ArticleMainImage = image_form.save(commit=False)
                main_img.article = article
                main_img.save()

            image_formset.instance = article
            image_formset.save()

        return super().form_valid(form)


class ArticleDeleteView(generic.DeleteView):  # type: ignore[type-arg]
    model = Article
    template_name = "news/article_confirm_delete.html"
    success_url = reverse_lazy("news:article_list")

    @classmethod
    def as_view(cls, **kwargs: Any) -> Any:
        view = super().as_view(**kwargs)
        return role_required(*_EDITOR_ROLES)(view)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["show_search"] = False
        return ctx
