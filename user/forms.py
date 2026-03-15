from django import forms
from django.contrib.auth.forms import UserCreationForm

from user.models import User


class ProfileEditForm(forms.ModelForm):
    """Form for editing user profile (email, name, avatar)."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "avatar")
        widgets = {
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ім'я",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Прізвище",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Електронна пошта",
                }
            ),
            "avatar": forms.FileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/*",
                }
            ),
        }
        labels = {
            "first_name": "",
            "last_name": "",
            "email": "",
            "avatar": "Аватар",
        }


class SignUpForm(UserCreationForm):
    """User registration form with email-based authentication.

    Поля реєстрації:
      - email — обов'язковий, унікальний логін користувача.
      - first_name, last_name — необов'язкові.
      - password1, password2 — пароль та підтвердження.

    username не показується — генерується автоматично з email у User.save().

    Документація UserCreationForm:
      https://docs.djangoproject.com/en/stable/topics/auth/default/#django.contrib.auth.forms.UserCreationForm
    """

    class Meta:
        model = User
        # email — обов'язковий для входу, first_name/last_name — необов'язкові.
        # username не включаємо — він генерується автоматично з email.
        fields = ("email", "first_name", "last_name")
        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Електронна пошта (обов'язково)",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ім'я (необов'язково)",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Прізвище (необов'язково)",
                }
            ),
        }
        labels = {
            "email": "",
            "first_name": "",
            "last_name": "",
        }
        help_texts = {
            "email": "",
        }

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        # password1 і password2 визначені в UserCreationForm, не в Meta,
        # тому налаштовуємо через __init__.
        self.fields["password1"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Пароль (мінімум 8 символів, не лише цифри)",
            }
        )
        self.fields["password1"].label = ""
        self.fields["password1"].help_text = ""
        self.fields["password2"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Підтвердження пароля",
            }
        )
        self.fields["password2"].label = ""
        self.fields["password2"].help_text = ""
