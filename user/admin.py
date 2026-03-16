from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        "email",
        "username",
        "role",
        "display_title",
        "public_name",
        "is_active",
    ]
    list_filter = ["role", "is_active"]
    search_fields = ["email", "username", "first_name", "public_name"]
    fieldsets = (
        *(BaseUserAdmin.fieldsets or ()),
        (
            "Профіль для відвідувачів",
            {
                "fields": ("display_title", "public_name"),
                "description": "Ці поля бачитимуть відвідувачі при відстеженні замовлення.",
            },
        ),
        (
            "Роль та аватар",
            {"fields": ("role", "avatar")},
        ),
    )
