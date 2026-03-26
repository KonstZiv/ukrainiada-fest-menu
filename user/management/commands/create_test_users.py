"""Create test users for development/staging environments."""

from __future__ import annotations

import secrets
from typing import Any

from django.core.management.base import BaseCommand

from core_settings.settings.env import config
from user.models import CommunicationChannel, User

TEST_USERS = [
    {"email": "manager@fest.ua", "role": "manager", "first_name": "Manager"},
    {"email": "senior@fest.ua", "role": "senior_waiter", "first_name": "Senior"},
    {"email": "dmytro@fest.ua", "role": "waiter", "first_name": "Dmytro"},
    {"email": "valentyna@fest.ua", "role": "kitchen", "first_name": "Valentyna"},
]


class Command(BaseCommand):
    help = (
        "Create test users. Password from TEST_USER_PASSWORD env var or auto-generated."
    )

    def handle(self, **options: Any) -> None:
        password = config("TEST_USER_PASSWORD", default="")
        if not password:
            password = secrets.token_urlsafe(12)
            self.stdout.write(self.style.WARNING(f"Generated password: {password}"))

        for data in TEST_USERS:
            user, created = User.objects.get_or_create(
                email=data["email"],
                defaults={
                    "role": data["role"],
                    "first_name": data["first_name"],
                    "is_staff": data["role"] == "manager",
                },
            )
            if created:
                user.set_password(password)
                user.save()
                self.stdout.write(f"  {data['email']} ({data['role']}) — created")
            else:
                self.stdout.write(f"  {data['email']} — already exists")

            CommunicationChannel.objects.get_or_create(
                user=user,
                channel_type=CommunicationChannel.ChannelType.EMAIL,
                defaults={"address": user.email, "is_verified": True, "priority": 0},
            )

        self.stdout.write(self.style.SUCCESS("Done."))
