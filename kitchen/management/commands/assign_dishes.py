"""Assign all dishes to all kitchen users (idempotent)."""

from django.core.management.base import BaseCommand

from kitchen.models import KitchenAssignment
from menu.models import Dish
from user.models import User


class Command(BaseCommand):
    help = "Assign all dishes to all kitchen users (idempotent, safe to re-run)."

    def handle(self, **options: object) -> None:
        kitchen_users = User.objects.filter(role__in=["kitchen", "kitchen_supervisor"])
        dishes = Dish.objects.all()

        if not kitchen_users.exists():
            self.stdout.write(self.style.WARNING("No kitchen users found."))
            return

        created = 0
        for user in kitchen_users:
            for dish in dishes:
                _, is_new = KitchenAssignment.objects.get_or_create(
                    kitchen_user=user, dish=dish
                )
                if is_new:
                    created += 1

        total = KitchenAssignment.objects.count()
        self.stdout.write(
            self.style.SUCCESS(f"Done: {created} new assignments, {total} total.")
        )
