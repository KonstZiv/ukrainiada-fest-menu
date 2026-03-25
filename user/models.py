from __future__ import annotations

from io import BytesIO
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.files.base import ContentFile
from django.db import models
from django.utils.translation import gettext_lazy as _
from PIL import Image


class User(AbstractUser):
    """Extended user model with email-based authentication.

    Ключова зміна відносно стандартного AbstractUser:
      - email — унікальне обов'язкове поле, використовується для входу.
      - username — необов'язкове, генерується з email якщо не задане.
      - USERNAME_FIELD = "email" — Django використовує email для автентифікації.
      - REQUIRED_FIELDS = ["username"] — createsuperuser запитає username.

    Avatar image is automatically cropped and resized on save
    according to ``settings.USER_AVATAR_ASPECT_RATIO`` and
    ``settings.USER_AVATAR_MAX_PIXELS``.

    Документація:
      https://docs.djangoproject.com/en/stable/topics/auth/customizing/#substituting-a-custom-user-model
    """

    # ---------------------------------------------------------------------------
    # Перевизначення полів AbstractUser для email-based автентифікації
    # ---------------------------------------------------------------------------

    # email — тепер унікальний і обов'язковий (замість username).
    # AbstractUser має email без unique=True, тому перевизначаємо.
    email = models.EmailField(
        unique=True,
        verbose_name=_("Електронна пошта"),
    )

    # username — необов'язковий. Якщо не заповнений — генерується з email.
    # blank=True дозволяє залишити порожнім у формах.
    # AbstractUser має username з unique=True, тому зберігаємо цю поведінку.
    username = models.CharField(
        max_length=150,
        unique=True,
        blank=True,
        verbose_name=_("Ім'я користувача"),
    )

    # USERNAME_FIELD — поле, яке Django використовує для автентифікації.
    # За замовчуванням "username", ми змінюємо на "email".
    # Документація:
    #   https://docs.djangoproject.com/en/stable/topics/auth/customizing/#django.contrib.auth.models.CustomUser.USERNAME_FIELD
    USERNAME_FIELD = "email"

    # REQUIRED_FIELDS — додаткові поля при createsuperuser (окрім USERNAME_FIELD і password).
    # username тут обов'язковий для createsuperuser, але не для звичайної реєстрації.
    REQUIRED_FIELDS = ["username"]

    class RegistrationSource(models.TextChoices):
        """How the user originally registered."""

        EMAIL = "email", "Email"
        GOOGLE = "google", "Google"
        FACEBOOK = "facebook", "Facebook"
        INSTAGRAM = "instagram", "Instagram"
        TELEGRAM = "telegram", "Telegram"

    class Role(models.TextChoices):
        """User roles within the platform."""

        MANAGER = "manager", _("Менеджер")
        KITCHEN_SUPERVISOR = "kitchen_supervisor", _("Старший кухні")
        KITCHEN = "kitchen", _("Виробництво")
        SENIOR_WAITER = "senior_waiter", _("Старший офіціант")
        WAITER = "waiter", _("Офіціант")
        EDITOR = "editor", _("Редактор")
        CORRECTOR = "corrector", _("Коректор")
        VISITOR = "visitor", _("Відвідувач")

    avatar = models.ImageField(
        upload_to="user_avatars/",
        blank=True,
        verbose_name=_("Аватар"),
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.VISITOR,
        verbose_name=_("Роль"),
    )

    display_title = models.CharField(
        max_length=60,
        blank=True,
        verbose_name=_("Посада для відвідувачів"),
        help_text=_("Наприклад: Повариха, Бармен, Майстер десертів"),
    )

    public_name = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Публічне ім'я"),
        help_text=_("Ім'я без прізвища для відвідувачів"),
    )

    registration_source = models.CharField(
        max_length=20,
        choices=RegistrationSource.choices,
        default=RegistrationSource.EMAIL,
        verbose_name=_("Джерело реєстрації"),
    )

    corrector_languages: models.JSONField[list[str], list[str]] = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Мови коректора"),
        help_text=_("Коди мов для коректури: en, cnr, hr, bs, it, de"),
    )

    @property
    def staff_label(self) -> str:
        """Human-friendly label for visitor-facing displays.

        Examples:
            'Повариха Валентина'  — display_title + public_name
            'Виробництво Дмитро'  — role display + first_name (fallback)
            'Офіціант john'       — role display + email prefix (last fallback)

        """
        title = self.display_title or self.get_role_display()
        name = self.public_name or self.first_name or self.email.split("@")[0]
        return f"{title} {name}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save user, generate username from email if needed, process avatar.

        Якщо username не заданий — беремо частину email до символу @.
        Наприклад: "john.doe@gmail.com" → "john.doe".
        Якщо такий username вже зайнятий — додаємо числовий суфікс.
        """
        if not self.username:
            base = self.email.split("@")[0]
            candidate = base
            counter = 1
            while User.objects.filter(username=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}{counter}"
                counter += 1
            self.username = candidate
        super().save(*args, **kwargs)
        if self.avatar:
            self._process_avatar()

    def _process_avatar(self) -> None:
        """Crop and resize avatar according to project settings.

        Crop logic:
            If ``min_side / max_side < USER_AVATAR_ASPECT_RATIO``,
            the longer side is trimmed symmetrically from both edges
            so that the ratio becomes exactly ``USER_AVATAR_ASPECT_RATIO``.

        Resize logic:
            If the longer side exceeds ``USER_AVATAR_MAX_PIXELS``,
            the image is proportionally downscaled.
        """
        img: Image.Image = Image.open(self.avatar.path)
        width, height = img.size
        changed = False

        # --- Обрізка до мінімального aspect ratio ---
        min_ratio: float = settings.USER_AVATAR_ASPECT_RATIO
        current_ratio = min(width, height) / max(width, height)

        if current_ratio < min_ratio:
            if width > height:
                # Горизонтальне зображення — обрізаємо ширину
                new_width = int(height / min_ratio)
                offset = (width - new_width) // 2
                img = img.crop((offset, 0, offset + new_width, height))
            else:
                # Вертикальне зображення — обрізаємо висоту
                new_height = int(width / min_ratio)
                offset = (height - new_height) // 2
                img = img.crop((0, offset, width, offset + new_height))
            width, height = img.size
            changed = True

        # --- Зменшення до максимального розміру ---
        max_px: int = settings.USER_AVATAR_MAX_PIXELS
        if max(width, height) > max_px:
            img.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
            changed = True

        if changed:
            buffer = BytesIO()
            img_format = img.format or "PNG"
            img.save(buffer, format=img_format)
            self.avatar.save(
                self.avatar.name,
                ContentFile(buffer.getvalue()),
                save=False,
            )
            # save=False вище, тому зберігаємо лише поле avatar
            super().save(update_fields=["avatar"])


class CommunicationChannel(models.Model):
    """User communication channel for notifications and digests."""

    class ChannelType(models.TextChoices):
        EMAIL = "email", _("Email")
        TELEGRAM = "telegram", _("Telegram")

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="channels",
    )
    channel_type = models.CharField(
        max_length=20,
        choices=ChannelType.choices,
        verbose_name=_("Тип каналу"),
    )
    address = models.CharField(
        max_length=255,
        verbose_name=_("Адреса"),
        help_text=_("Email, Telegram chat ID, або номер телефону"),
    )
    is_verified = models.BooleanField(
        default=False,
        verbose_name=_("Верифіковано"),
    )
    priority = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_("Пріоритет"),
        help_text=_("Менше число — вищий пріоритет"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "channel_type"],
                name="unique_channel_per_type",
            ),
        ]
        ordering = ["priority"]
        verbose_name = _("Канал комунікації")
        verbose_name_plural = _("Канали комунікації")

    def __str__(self) -> str:
        status = "\u2713" if self.is_verified else "\u2717"
        return f"{self.get_channel_type_display()} [{status}] {self.address}"
