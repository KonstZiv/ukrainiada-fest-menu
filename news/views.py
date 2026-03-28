"""Views for news articles — public list/detail and editor CRUD."""

from __future__ import annotations

from typing import Any, cast

from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views import generic

from news.forms import (
    ArticleForm,
    ArticleImageFormSet,
    ArticleMainImageForm,
    CommentForm,
)
from news.models import (
    Article,
    ArticleComment,
    ArticleMainImage,
    DigestSubscription,
    TranslationFeedback,
)
from translations.models import TranslationApproval
from user.decorators import role_required, verified_channel_required
from user.models import User

_EDITOR_ROLES = ("editor", "manager")


# ---------------------------------------------------------------------------
# Public views
# ---------------------------------------------------------------------------


def article_list(request: HttpRequest) -> HttpResponse:
    """Public list of published articles; editors see all statuses."""
    qs = Article.objects.select_related(
        "main_image", "primary_tag", "author"
    ).prefetch_related("tags")

    user = request.user
    is_editor = user.is_authenticated and cast(User, user).role in _EDITOR_ROLES
    if not is_editor:
        qs = qs.filter(status=Article.Status.PUBLISHED)

    return render(
        request,
        "news/article_list.html",
        {"articles": qs, "is_editor": is_editor, "show_search": False},
    )


def article_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Public article detail with full content."""
    qs: QuerySet[Article] = Article.objects.select_related(
        "main_image", "primary_tag", "author"
    ).prefetch_related("tags", "images")

    # Editors/managers see all statuses; visitors only published.
    user = request.user
    if user.is_authenticated and cast(User, user).role in _EDITOR_ROLES:
        article = get_object_or_404(qs, pk=pk)
    else:
        article = get_object_or_404(qs, pk=pk, status=Article.Status.PUBLISHED)

    # Check if translation is approved for current language.
    current_lang = get_language() or "uk"
    translation_approved = current_lang == "uk"
    if not translation_approved:
        ct = ContentType.objects.get_for_model(Article)
        translation_approved = TranslationApproval.objects.filter(
            content_type=ct,
            object_id=article.pk,
            language=current_lang,
            status=TranslationApproval.Status.APPROVED,
        ).exists()

    # Comments: approved for everyone, pending also visible to editor/manager.
    comments = article.comments.select_related("author")
    user = request.user
    if not (user.is_authenticated and cast(User, user).role in _EDITOR_ROLES):
        comments = comments.filter(status=ArticleComment.Status.APPROVED)

    # Comment form for authenticated users with verified channel.
    comment_form = None
    can_comment = False
    if user.is_authenticated:
        u = cast(User, user)
        can_comment = u.channels.filter(is_verified=True).exists()
        if can_comment:
            comment_form = CommentForm()

    return render(
        request,
        "news/article_detail.html",
        {
            "article": article,
            "show_search": False,
            "translation_approved": translation_approved,
            "comments": comments,
            "comment_form": comment_form,
            "can_comment": can_comment,
        },
    )


# ---------------------------------------------------------------------------
# Editor CRUD
# ---------------------------------------------------------------------------


@role_required(*_EDITOR_ROLES)
def toggle_article_status(request: HttpRequest, pk: int) -> HttpResponse:
    """Toggle article between draft and published."""
    if request.method != "POST":
        return redirect("news:article_list")

    article = get_object_or_404(Article, pk=pk)
    if article.status == Article.Status.DRAFT:
        article.status = Article.Status.PUBLISHED
        article.save(update_fields=["status"])
        messages.success(request, _("Статтю опубліковано."))
    elif article.status == Article.Status.PUBLISHED:
        article.status = Article.Status.DRAFT
        article.save(update_fields=["status"])
        messages.info(request, _("Статтю приховано."))

    return redirect("news:article_list")


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

        # Trigger urgent notification if applicable.
        if article.is_urgent and article.status == Article.Status.PUBLISHED:
            from news.tasks import send_urgent_notification

            try:
                send_urgent_notification.delay(article.pk)
            except Exception:
                pass  # Celery unavailable in dev/test

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


# ---------------------------------------------------------------------------
# Translation feedback
# ---------------------------------------------------------------------------


def submit_translation_feedback(request: HttpRequest, pk: int) -> HttpResponse:
    """Submit feedback about a translation inaccuracy."""
    article = get_object_or_404(Article, pk=pk)

    if request.method == "POST":
        message = request.POST.get("message", "").strip()
        if message:
            TranslationFeedback.objects.create(
                article=article,
                language=get_language() or "uk",
                message=message,
                page_url=request.build_absolute_uri(article.get_absolute_url())
                if hasattr(article, "get_absolute_url")
                else request.META.get("HTTP_REFERER", ""),
                user=request.user if request.user.is_authenticated else None,
            )
            messages.success(request, _("Дякуємо за зауваження!"))
        return redirect("news:article_detail", pk=pk)

    return redirect("news:article_detail", pk=pk)


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


@verified_channel_required
def submit_comment(request: HttpRequest, pk: int) -> HttpResponse:
    """Submit a comment on an article (pre-moderated)."""
    article = get_object_or_404(Article, pk=pk, status=Article.Status.PUBLISHED)

    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.article = article
            comment.author = cast(User, request.user)
            comment.save()
            messages.success(request, _("Коментар надіслано на модерацію."))

    return redirect("news:article_detail", pk=pk)


@role_required(*_EDITOR_ROLES)
def moderate_comments(request: HttpRequest) -> HttpResponse:
    """List all pending comments for moderation."""
    pending = (
        ArticleComment.objects.filter(status=ArticleComment.Status.PENDING)
        .select_related("article", "author")
        .order_by("-created_at")
    )
    return render(
        request,
        "news/moderate_comments.html",
        {"comments": pending, "show_search": False},
    )


@role_required(*_EDITOR_ROLES)
def approve_comment(request: HttpRequest, pk: int) -> HttpResponse:
    """Approve a pending comment."""
    comment = get_object_or_404(ArticleComment, pk=pk)
    comment.status = ArticleComment.Status.APPROVED
    comment.moderated_by = cast(User, request.user)
    comment.save(update_fields=["status", "moderated_by"])
    messages.success(request, _("Коментар схвалено."))
    return redirect("news:moderate_comments")


@role_required(*_EDITOR_ROLES)
def reject_comment(request: HttpRequest, pk: int) -> HttpResponse:
    """Reject a pending comment."""
    comment = get_object_or_404(ArticleComment, pk=pk)
    comment.status = ArticleComment.Status.REJECTED
    comment.moderated_by = cast(User, request.user)
    comment.save(update_fields=["status", "moderated_by"])
    messages.info(request, _("Коментар відхилено."))
    return redirect("news:moderate_comments")


# ---------------------------------------------------------------------------
# Digest subscription
# ---------------------------------------------------------------------------


@verified_channel_required
def manage_subscription(request: HttpRequest) -> HttpResponse:
    """Subscribe/unsubscribe from news digests."""
    user = cast(User, request.user)
    sub, _ = DigestSubscription.objects.get_or_create(user=user)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "update":
            frequency = request.POST.get("frequency", "weekly")
            if frequency in dict(DigestSubscription.Frequency.choices):  # type: ignore[operator]
                sub.frequency = frequency
                sub.is_active = True
                sub.save(update_fields=["frequency", "is_active"])
                messages.success(request, _("Підписку оновлено."))
        elif action == "unsubscribe":
            sub.is_active = False
            sub.save(update_fields=["is_active"])
            messages.info(request, _("Підписку деактивовано."))
        elif action == "resubscribe":
            sub.is_active = True
            sub.save(update_fields=["is_active"])
            messages.success(request, _("Підписку відновлено."))
        return redirect("news:subscription")

    return render(
        request,
        "news/subscription.html",
        {
            "subscription": sub,
            "frequencies": DigestSubscription.Frequency.choices,  # type: ignore[operator]
            "show_search": False,
        },
    )
