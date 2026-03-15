import os
from pathlib import Path

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_settings.settings.dev")
django.setup()

from django.core.files import File  # noqa: E402
from django.db import transaction  # noqa: E402

from menu.models import Tag, TagLogo  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent
LOGOS_DIR = SCRIPT_DIR / "doc" / "design" / "tag-logo-svg"

tags_data = [
    {
        "title": "Українська кухня",
        "file": "ukrainian-cuisine.svg",
        "desc": "Рідні смаки, що зігрівають серце: від духмяного борщу до золотистих вареників.",
    },
    {
        "title": "Чорногорська кухня",
        "file": "montenegrin-cuisine.svg",
        "desc": "Справжній смак гір та полонин: традиційні м'ясні та сирні шедеври за старовинними рецептами.",
    },
    {
        "title": "Бокельська кухня",
        "file": "bokel-cousine.svg",
        "desc": "Унікальний міст між морем та історією — вишукане поєднання адріатичних традицій Которської затоки.",
    },
    {
        "title": "Середземноморська кухня",
        "file": "miditerranean-cuisine.svg",
        "desc": "Сонце у кожній тарілці: легкість оливкової олії, свіжість трав та багатство морепродуктів.",
    },
    {
        "title": "Вибір Шефа",
        "file": "cieff-recomended.svg",
        "desc": "Наша гордість та рекомендація: страви, в які шеф-кухар вклав свій талант та натхнення.",
    },
    {
        "title": "Сезонна страва",
        "file": "seasonal-dish.svg",
        "desc": "Найкраще від природи саме зараз: готуємо з найсвіжіших продуктів поточного сезону.",
    },
    {
        "title": "Дитяче меню",
        "file": "for-kids-2.svg",
        "desc": "Здорово, корисно та весело: спеціально розроблені страви, що неодмінно сподобаються малечі.",
    },
    {
        "title": "Веганська страва",
        "file": "vegan.svg",
        "desc": "Абсолютна гармонія рослинних інгредієнтів без жодного продукту тваринного походження.",
    },
    {
        "title": "Вегетаріанська страва",
        "file": "vegetarian.svg",
        "desc": "Збалансоване поєднання овочів, злаків та молочних продуктів для вашої енергії.",
    },
    {
        "title": "Без цукру",
        "file": "sugar-free.svg",
        "desc": "Природна насолода без шкоди для здоров'я — ідеальний вибір для тих, хто дбає про себе.",
    },
    {
        "title": "Без глютену",
        "file": "gluten-free.svg",
        "desc": "Безпечне та повноцінне харчування для тих, хто обирає життя без клейковини.",
    },
    {
        "title": "Без лактози",
        "file": "lactose-free.svg",
        "desc": "Легкість у кожному шматочку: ми дбаємо про ваш комфорт та особливості раціону.",
    },
    {
        "title": "Без горіхів",
        "file": "without-nuts.svg",
        "desc": "Безпечний вибір: гарантуємо відсутність горіхів у складі для вашого спокою.",
    },
    {
        "title": "Гостро",
        "file": "spicy.svg",
        "desc": "Для любителів яскравих вражень: пікантний смак із характером та вогником.",
    },
    {
        "title": "Пасує до вина",
        "file": "goes-well-with-wine.svg",
        "desc": "Ідеальний гастрономічний тандем, що розкриває найкращі ноти вашого напою.",
    },
]

print("--- Починаємо заповнення тегів ---")

with transaction.atomic():
    for item in tags_data:
        file_path = os.path.join(LOGOS_DIR, item["file"])

        # 1. Тег
        tag, created = Tag.objects.get_or_create(
            title=item["title"], defaults={"description": item["desc"]}
        )
        if not created:
            tag.description = item["desc"]
            tag.save()

        # 2. Логотип тегу
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                logo_obj, logo_created = TagLogo.objects.get_or_create(
                    tag=tag, defaults={"title": f"Logo {item['title']}"}
                )
                logo_obj.image.save(item["file"], File(f), save=True)
            print(f"✅ Тег '{item['title']}' додано.")
        else:
            print(f"⚠️ Файл не знайдено: {file_path}")

print("--- Заповнення тегів завершено! ---")
