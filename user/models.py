from __future__ import annotations

from io import BytesIO
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.files.base import ContentFile
from django.db import models
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
        verbose_name="Електронна пошта",
    )

    # username — необов'язковий. Якщо не заповнений — генерується з email.
    # blank=True дозволяє залишити порожнім у формах.
    # AbstractUser має username з unique=True, тому зберігаємо цю поведінку.
    username = models.CharField(
        max_length=150,
        unique=True,
        blank=True,
        verbose_name="Ім'я користувача",
    )

    # USERNAME_FIELD — поле, яке Django використовує для автентифікації.
    # За замовчуванням "username", ми змінюємо на "email".
    # Документація:
    #   https://docs.djangoproject.com/en/stable/topics/auth/customizing/#django.contrib.auth.models.CustomUser.USERNAME_FIELD
    USERNAME_FIELD = "email"

    # REQUIRED_FIELDS — додаткові поля при createsuperuser (окрім USERNAME_FIELD і password).
    # username тут обов'язковий для createsuperuser, але не для звичайної реєстрації.
    REQUIRED_FIELDS = ["username"]

    class Role(models.TextChoices):
        """User roles within the restaurant system."""

        MANAGER = "manager", "Менеджер"
        KITCHEN_SUPERVISOR = "kitchen_supervisor", "Старший кухні"
        KITCHEN = "kitchen", "Виробництво"
        SENIOR_WAITER = "senior_waiter", "Старший офіціант"
        WAITER = "waiter", "Офіціант"
        VISITOR = "visitor", "Відвідувач"

    avatar = models.ImageField(
        upload_to="user_avatars/",
        blank=True,
        verbose_name="Аватар",
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.VISITOR,
        verbose_name="Роль",
    )

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
