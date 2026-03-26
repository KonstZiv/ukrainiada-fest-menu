"""Configure django.contrib.sites Site with correct domain."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Set Site domain and name for django-allauth OAuth callbacks."

    def handle(self, **options: Any) -> None:
        domain = getattr(settings, "SITE_DOMAIN", "localhost:8000")
        site, _ = Site.objects.get_or_create(id=settings.SITE_ID)
        site.domain = domain
        site.name = "Dobro Djelo"
        site.save()
        self.stdout.write(
            self.style.SUCCESS(f"Site #{site.id}: {site.domain} ({site.name})")
        )
