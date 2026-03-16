"""Add access_token to Order (two-step for existing rows)."""

import uuid

from django.db import migrations, models


def populate_tokens(apps, schema_editor):  # type: ignore[no-untyped-def]
    """Generate unique UUID tokens for existing orders."""
    Order = apps.get_model("orders", "Order")
    for order in Order.objects.filter(access_token__isnull=True):
        order.access_token = uuid.uuid4()
        order.save(update_fields=["access_token"])


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0004_add_location_hint"),
    ]

    operations = [
        # Step 1: add nullable field
        migrations.AddField(
            model_name="order",
            name="access_token",
            field=models.UUIDField(null=True, db_index=True),
        ),
        # Step 2: populate existing rows
        migrations.RunPython(populate_tokens, migrations.RunPython.noop),
        # Step 3: make non-nullable with default and unique
        migrations.AlterField(
            model_name="order",
            name="access_token",
            field=models.UUIDField(
                default=uuid.uuid4, unique=True, db_index=True, editable=False
            ),
        ),
    ]
