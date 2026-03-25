"""Views for translation review and approval workflow."""

from __future__ import annotations

from typing import cast

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from translations.constants import FIELDS_MAP, TARGET_LANGUAGES
from translations.models import TranslationApproval
from translations.services import (
    approve_all_for_object,
    approve_translation,
    get_pending_objects,
    retry_translation,
    save_edited_translation,
)
from user.decorators import role_required
from user.models import User

_REVIEW_ROLES = ("manager", "kitchen_supervisor", "senior_waiter")


@role_required(*_REVIEW_ROLES)
def review_list(request: HttpRequest) -> HttpResponse:
    """Show all objects with pending / failed translations."""
    objects = get_pending_objects()
    return render(
        request,
        "translations/review.html",
        {
            "objects": objects,
            "target_languages": TARGET_LANGUAGES,
            "show_search": False,
        },
    )


@require_POST
@role_required(*_REVIEW_ROLES)
def approve_single(request: HttpRequest, pk: int) -> HttpResponse:
    """Approve one translation (one language for one object)."""
    approval = get_object_or_404(TranslationApproval, pk=pk)
    user = cast(User, request.user)
    approve_translation(approval, user)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "status": "approved"})
    return redirect("translations:review")


@require_POST
@role_required(*_REVIEW_ROLES)
def approve_all(request: HttpRequest) -> HttpResponse:
    """Approve all pending translations for one object."""
    from django.contrib.contenttypes.models import ContentType

    ct_id = int(request.POST["content_type_id"])
    obj_id = int(request.POST["object_id"])
    ct = get_object_or_404(ContentType, pk=ct_id)
    user = cast(User, request.user)
    count = approve_all_for_object(ct, obj_id, user)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "approved_count": count})
    return redirect("translations:review")


@role_required(*_REVIEW_ROLES)
def edit_translation(request: HttpRequest, pk: int) -> HttpResponse:
    """Edit a translation and auto-approve on save."""
    approval = get_object_or_404(
        TranslationApproval.objects.select_related("content_type"),
        pk=pk,
    )
    ct = approval.content_type
    model = ct.model_class()
    if model is None:
        return redirect("translations:review")

    obj = get_object_or_404(model, pk=approval.object_id)
    fields: list[str] = list(FIELDS_MAP.get(model, {}))

    if request.method == "POST":
        field_values = {f: request.POST.get(f, "") for f in fields}
        user = cast(User, request.user)
        save_edited_translation(approval, field_values, user)
        return redirect("translations:review")

    # GET — show edit form.
    current_values = {f: getattr(obj, f"{f}_{approval.language}", "") for f in fields}
    source_values = {f: getattr(obj, f"{f}_uk", "") for f in fields}

    return render(
        request,
        "translations/edit.html",
        {
            "approval": approval,
            "object": obj,
            "model_name": ct.model.capitalize(),
            "language": approval.language,
            "fields": fields,
            "current_values": current_values,
            "source_values": source_values,
            "show_search": False,
        },
    )


@require_POST
@role_required(*_REVIEW_ROLES)
def retry_failed(request: HttpRequest, pk: int) -> HttpResponse:
    """Re-trigger Gemini translation for a failed approval."""
    approval = get_object_or_404(TranslationApproval, pk=pk)
    retry_translation(approval)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "status": "retrying"})
    return redirect("translations:review")
