# ---------------------------------------------------------------------------
# Data migration: populate number_in_line for existing categories.
#
# Data migration — міграція, яка змінює ДАНІ, а не структуру таблиці.
# Використовується RunPython з двома функціями:
#   - forward  — застосовує зміни (заповнює number_in_line)
#   - backward — скасовує зміни (скидає number_in_line на 0)
#
# apps.get_model() — безпечний спосіб отримати модель у міграції,
# бо використовує "заморожений" стан моделі на момент цієї міграції.
#
# Документація:
#   https://docs.djangoproject.com/en/stable/topics/migrations/#data-migrations
#   https://docs.djangoproject.com/en/stable/ref/migration-operations/#runpython
# ---------------------------------------------------------------------------

from django.db import migrations

# Словник {title: number_in_line} — логічний порядок категорій у меню.
# Салати → перші страви → м'ясо → морепродукти → гарніри → випічка →
# десерти → холодні напої → гарячі напої → пиво → вина → міцні напої.
CATEGORY_ORDER: dict[str, int] = {
    "Салати": 1,
    "Перші страви": 2,
    "М'ясні страви": 3,
    "Морепродукти": 4,
    "Гарніри": 5,
    "Випічка": 6,
    "Десерти": 7,
    "Холодні напої": 8,
    "Гарячі напої": 9,
    "Пиво": 10,
    "Вина": 11,
    "Міцні напої": 12,
}


def populate_order(apps, schema_editor):  # type: ignore[no-untyped-def]
    """Set number_in_line for each category based on CATEGORY_ORDER."""
    Category = apps.get_model("menu", "Category")
    for title, order in CATEGORY_ORDER.items():
        Category.objects.filter(title=title).update(number_in_line=order)


def reset_order(apps, schema_editor):  # type: ignore[no-untyped-def]
    """Reset number_in_line to 0 (reverse migration)."""
    Category = apps.get_model("menu", "Category")
    Category.objects.all().update(number_in_line=0)


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0002_add_category_number_in_line"),
    ]

    # RunPython(forward, reverse) — виконує Python-код при migrate / migrate --reverse.
    # Документація:
    #   https://docs.djangoproject.com/en/stable/ref/migration-operations/#runpython
    operations = [
        migrations.RunPython(populate_order, reset_order),
    ]
