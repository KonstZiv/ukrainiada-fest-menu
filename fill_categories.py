import os
from pathlib import Path

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_settings.settings.dev")
django.setup()

from django.core.files import File  # noqa: E402
from django.db import transaction  # noqa: E402

from menu.models import Category, CategoryLogo  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent
LOGOS_DIR = SCRIPT_DIR / "doc" / "design" / "cat-logo-svg"

categories_data = [
    {
        "title": "Перші страви",
        "file": "first-course.svg",
        "desc": "Традиційні та авторські супи, що зігрівають душу та дарують енергію.",
    },
    {
        "title": "М'ясні страви",
        "file": "meat-dishes.svg",
        "desc": "Соковиті стейки, ніжне філе та майстерно приготована дичина для справжніх гурманів.",
    },
    {
        "title": "Морепродукти",
        "file": "sea-food.svg",
        "desc": "Свіжий вилов, що пахне морем: від вишуканих креветок до ніжної морської риби.",
    },
    {
        "title": "Салати",
        "file": "salad.svg",
        "desc": "Хрусткі мікси свіжих овочів, зелені та авторських заправок для легкості та здоров'я.",
    },
    {
        "title": "Гарніри",
        "file": "side-dish.svg",
        "desc": "Ідеальне доповнення до основних страв: ароматна картопля, розсипчасті крупи та овочі гриль.",
    },
    {
        "title": "Випічка",
        "file": "baking.svg",
        "desc": "Домашній затишок у кожному шматочку: свіжоспечений хліб, булочки та пироги з печі.",
    },
    {
        "title": "Десерти",
        "file": "dessert.svg",
        "desc": "Солодкі шедеври, що стануть ідеальним фіналом вашої трапези.",
    },
    {
        "title": "Холодні напої",
        "file": "cold-drink.svg",
        "desc": "Освіжаючі лимонади, фреші та коктейлі, що дарують прохолоду в спекотний день.",
    },
    {
        "title": "Гарячі напої",
        "file": "hot-drinks.svg",
        "desc": "Ароматна кава та добірні сорти чаю для теплих розмов та бадьорого ранку.",
    },
    {
        "title": "Пиво",
        "file": "beer.svg",
        "desc": "Крафтові та класичні сорти пінного з найкращих броварень світу.",
    },
    {
        "title": "Вина",
        "file": "wine.svg",
        "desc": "Вишукана колекція вин, що розкривають смак кожної страви по-новому.",
    },
    {
        "title": "Міцні напої",
        "file": "spirt-drink.svg",
        "desc": "Благородний вибір для поціновувачів міцного характеру та чистого смаку.",
    },
]

print("--- Починаємо заповнення категорій ---")

# Використовуємо atomic, щоб або все збереглось, або нічого (якщо буде помилка)
with transaction.atomic():
    for item in categories_data:
        file_path = os.path.join(LOGOS_DIR, item["file"])

        # 1. Створюємо/оновлюємо категорію
        category, created = Category.objects.get_or_create(
            title=item["title"], defaults={"description": item["desc"]}
        )

        if not created:
            category.description = item["desc"]
            category.save()

        # 2. Обробка логотипу
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                # OneToOneField: get_or_create за категорією
                logo_obj, logo_created = CategoryLogo.objects.get_or_create(
                    category=category, defaults={"title": f"Logo {item['title']}"}
                )

                # Зберігаємо файл
                logo_obj.image.save(item["file"], File(f), save=True)

            print(f"✅ Категорія '{item['title']}' готова.")
        else:
            print(f"⚠️ Файл не знайдено: {file_path}")

print("--- Заповнення завершено! Перевіряйте БД. ---")
