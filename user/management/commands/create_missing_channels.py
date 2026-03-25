"""Create email CommunicationChannel for users that don't have one."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from user.models import CommunicationChannel, User


class Command(BaseCommand):
    help = "Create email communication channel for existing users that lack one."

    def handle(self, **options: Any) -> None:
        created = 0
        for user in User.objects.all():
            _, is_new = CommunicationChannel.objects.get_or_create(
                user=user,
                channel_type=CommunicationChannel.ChannelType.EMAIL,
                defaults={
                    "address": user.email,
                    "is_verified": True,
                    "priority": 0,
                },
            )
            if is_new:
                created += 1
                self.stdout.write(f"  {user.email} — created")

        self.stdout.write(self.style.SUCCESS(f"Done: {created} channels created."))
