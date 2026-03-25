"""Forms for news article CRUD."""

from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _
from django_ckeditor_5.widgets import CKEditor5Widget

from news.models import Article, ArticleImage, ArticleMainImage


class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = [
            "title",
            "description",
            "content",
            "topic",
            "tags",
            "status",
            "is_urgent",
            "in_rotation",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Заголовок статті")}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": _("Короткий опис для анонсу"),
                }
            ),
            "content": CKEditor5Widget(config_name="default"),
            "topic": forms.Select(attrs={"class": "form-select"}),
            "tags": forms.CheckboxSelectMultiple(),
            "status": forms.Select(attrs={"class": "form-select"}),
        }


class ArticleMainImageForm(forms.ModelForm):
    class Meta:
        model = ArticleMainImage
        fields = ["title", "image"]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Назва зображення")}
            ),
            "image": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": "image/*"}
            ),
        }


ArticleImageFormSet = inlineformset_factory(
    Article,
    ArticleImage,
    fields=["title", "image"],
    extra=1,
    can_delete=True,
    widgets={
        "title": forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Назва зображення")}
        ),
        "image": forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": "image/*"}
        ),
    },
)
