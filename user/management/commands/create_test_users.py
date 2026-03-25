"""Create test users for development/staging environments."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from user.models import CommunicationChannel, User

TEST_USERS = [
    {"email": "manager@fest.ua", "role": "manager", "first_name": "Manager"},
    {"email": "senior@fest.ua", "role": "senior_waiter", "first_name": "Senior"},
    {"email": "dmytro@fest.ua", "role": "waiter", "first_name": "Dmytro"},
    {"email": "valentyna@fest.ua", "role": "kitchen", "first_name": "Valentyna"},
]

DEFAULT_PASSWORD = "fest2026"


class Command(BaseCommand):
    help = "Create test users with known credentials (for staging/dev)."

    def handle(self, **options: Any) -> None:
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
                user.set_password(DEFAULT_PASSWORD)
                user.save()
                self.stdout.write(f"  {data['email']} ({data['role']}) — created")
            else:
                self.stdout.write(f"  {data['email']} — already exists")

            CommunicationChannel.objects.get_or_create(
                user=user,
                channel_type=CommunicationChannel.ChannelType.EMAIL,
                defaults={"address": user.email, "is_verified": True, "priority": 0},
            )

        self.stdout.write(
            self.style.SUCCESS(f"Done. Password for all: {DEFAULT_PASSWORD}")
        )
