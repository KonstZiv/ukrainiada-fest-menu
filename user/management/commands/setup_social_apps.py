"""Create Social Applications for allauth from environment variables."""

from __future__ import annotations

from typing import Any

from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand

from core_settings.settings.env import config


class Command(BaseCommand):
    help = "Create/update Social Applications for OAuth providers."

    def handle(self, **options: Any) -> None:
        site = Site.objects.get(id=settings.SITE_ID)

        providers = [
            {
                "provider": "google",
                "name": "Google",
                "client_id": config("GOOGLE_CLIENT_ID", default=""),
                "secret": config("GOOGLE_CLIENT_SECRET", default=""),
            },
            {
                "provider": "facebook",
                "name": "Facebook",
                "client_id": config("FB_APP_ID", default=""),
                "secret": config("FB_APP_SECRET", default=""),
            },
        ]

        for p in providers:
            if not p["client_id"]:
                self.stdout.write(f"  {p['name']}: skipped (no credentials)")
                continue

            app, created = SocialApp.objects.update_or_create(
                provider=p["provider"],
                defaults={
                    "name": p["name"],
                    "client_id": p["client_id"],
                    "secret": p["secret"],
                },
            )
            app.sites.add(site)
            action = "created" if created else "updated"
            self.stdout.write(self.style.SUCCESS(f"  {p['name']}: {action}"))

        self.stdout.write(self.style.SUCCESS("Done."))
