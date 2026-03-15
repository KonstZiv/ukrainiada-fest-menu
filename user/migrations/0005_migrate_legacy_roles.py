"""Data migration: map legacy roles to new ones.

production → kitchen, finance → visitor.
"""

from django.db import migrations


def migrate_roles(apps, schema_editor):  # type: ignore[no-untyped-def]
    User = apps.get_model("user", "User")
    User.objects.filter(role="production").update(role="kitchen")
    User.objects.filter(role="finance").update(role="visitor")


class Migration(migrations.Migration):
    dependencies = [("user", "0004_update_roles")]
    operations = [migrations.RunPython(migrate_roles, migrations.RunPython.noop)]
