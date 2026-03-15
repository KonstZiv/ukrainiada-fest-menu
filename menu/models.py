from __future__ import annotations

import uuid
from functools import partial
from pathlib import Path

from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.text import slugify

from menu.validators import validate_svg_content


def upload_image(
    instance: ModelWithTitle, filename: str | Path, folder: str | Path = "images"
) -> Path:
    filename = slugify(Path(filename).stem) + str(uuid.uuid4()) + Path(filename).suffix
    return Path(folder) / Path(filename)


class ModelWithTitle(models.Model):
    title = models.CharField(max_length=128)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.title


class Category(ModelWithTitle):
    """Menu category (e.g. Salads, Desserts, Drinks).

    Categories are displayed in the order defined by ``number_in_line``
    (ascending), then by ``title`` as a tie-breaker.

    Attributes:
        description: Short category description (up to 1024 chars).
        number_in_line: Manual sort position — lower values appear first.

    """

    description = models.CharField(max_length=1024)
    # --- Поле ручного сортування (таска 1.7) ---
    # PositiveSmallIntegerField — ціле число 0–32767, ідеально для порядку.
    # default=0 — нові категорії потрапляють на початок, поки не задати порядок.
    # Документація:
    #   https://docs.djangoproject.com/en/stable/ref/models/fields/#positivesmallintegerfield
    number_in_line = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Порядок у меню",
        help_text="Менше число — вище у списку",
    )

    class Meta:
        # ordering — список полів для ORDER BY за замовчуванням.
        # ["number_in_line", "title"] означає:
        #   1. Спочатку за number_in_line (ASC)
        #   2. При рівному number_in_line — за title (ASC)
        # Документація:
        #   https://docs.djangoproject.com/en/stable/ref/models/options/#ordering
        ordering = ["number_in_line", "title"]


class Dish(ModelWithTitle):
    class Availability(models.TextChoices):
        """Dish availability status for the menu."""

        AVAILABLE = "available", "В наявності"
        LOW = "low", "Закінчується — уточнюйте у офіціанта"
        OUT = "out", "Немає"

    description = models.CharField(max_length=1024)
    price = models.DecimalField(max_digits=5, decimal_places=2)
    weight = models.PositiveIntegerField()
    calorie = models.PositiveIntegerField()
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="dishes"
    )
    tags: models.ManyToManyField[Tag, Dish] = models.ManyToManyField(
        "Tag", related_name="dishes", blank=True
    )
    availability = models.CharField(
        max_length=16,
        choices=Availability.choices,
        default=Availability.AVAILABLE,
        db_index=True,
        verbose_name="Наявність",
    )


class Tag(ModelWithTitle):
    description = models.CharField(max_length=1024)


upload_to_categorylogo = partial(upload_image, folder="category_logos")


class CategoryLogo(ModelWithTitle):
    # --- Валідатори поля image (таска 2.4) --- #
    # Два рівні захисту:
    #   1. FileExtensionValidator — перевіряє розширення файлу (.svg)
    #      Швидка перевірка, але ненадійна: файл можна перейменувати.
    #   2. validate_svg_content — перевіряє ВМІСТ файлу (заголовок <svg>)
    #      Надійна перевірка: навіть перейменований .png не пройде.
    # Документація:
    #   https://docs.djangoproject.com/en/stable/ref/validators/
    image = models.FileField(
        upload_to=upload_to_categorylogo,
        validators=[
            FileExtensionValidator(allowed_extensions=["svg"]),
            validate_svg_content,
        ],
        verbose_name="Vector logo (SVG)",
        help_text="Only upload .svg files, which allow for high-quality scaling without loss of clarity.",
    )
    category = models.OneToOneField(
        Category, on_delete=models.CASCADE, related_name="logo"
    )


upload_to_taglogo = partial(upload_image, folder="tag_logos")


class TagLogo(ModelWithTitle):
    # --- Валідатори аналогічні CategoryLogo (таска 2.5) --- #
    # Перевикористовуємо validate_svg_content — один валідатор для двох моделей (DRY).
    # Рівень 1: FileExtensionValidator — перевіряє розширення (.svg)
    # Рівень 2: validate_svg_content — перевіряє вміст файлу (<svg> або <?xml>)
    image = models.FileField(
        upload_to=upload_to_taglogo,
        validators=[
            FileExtensionValidator(allowed_extensions=["svg"]),
            validate_svg_content,
        ],
        verbose_name="Vector logo (SVG)",
        help_text="Only upload .svg files, which allow for high-quality scaling without loss of clarity.",
    )
    tag = models.OneToOneField(Tag, on_delete=models.CASCADE, related_name="logo")


upload_to_dish_main_image = partial(upload_image, folder="dish_main_images")


class DishMainImage(ModelWithTitle):
    image = models.ImageField(
        upload_to=upload_to_dish_main_image,
        verbose_name="Main dish image, recommended sizes 640x480px",
    )
    dish = models.OneToOneField(
        Dish, on_delete=models.CASCADE, related_name="main_image"
    )


upload_to_dish_picture = partial(upload_image, folder="dish_pictures")


class DishPicture(ModelWithTitle):
    image = models.ImageField(
        upload_to=upload_to_dish_picture,
        verbose_name="Additional dish image, recommended sizes 640x480px",
    )
    dish = models.ForeignKey(
        Dish, on_delete=models.CASCADE, related_name="additional_images"
    )
