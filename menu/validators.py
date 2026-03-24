# ---------------------------------------------------------------------------
# validators.py — Кастомні валідатори застосунку menu (таска 2.4)
#
# Що таке валідатор?
#   Валідатор — це callable (функція або клас з __call__), який приймає
#   значення і піднімає ValidationError, якщо значення невалідне.
#   Якщо значення валідне — нічого не повертає (None).
#
# Як Django використовує валідатори:
#   1. Валідатор додається до поля моделі: validators=[validate_svg_content]
#   2. При виклику form.is_valid() Django послідовно викликає кожен валідатор
#   3. Якщо валідатор підняв ValidationError — помилка додається до form.errors
#   4. Валідатори НЕ впливають на БД (це Python-логіка, не SQL constraint)
#   5. Тому зміна валідаторів НЕ потребує міграцій!
#
# Два рівні валідації файлів:
#   1. FileExtensionValidator — перевіряє РОЗШИРЕННЯ (.svg, .png тощо)
#      Проблема: файл "virus.png" перейменований у "virus.svg" пройде!
#   2. validate_svg_content — перевіряє ВМІСТ файлу (заголовок <svg> або <?xml>)
#      Надійніше: навіть якщо розширення правильне, вміст має бути SVG.
#
# Документація:
#   https://docs.djangoproject.com/en/stable/ref/validators/
#   https://docs.djangoproject.com/en/stable/ref/forms/validation/
# ---------------------------------------------------------------------------

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext_lazy as _


def validate_svg_content(file: UploadedFile) -> None:
    """Validate that the uploaded file contains valid SVG content.

    Перевіряємо що файл починається з SVG-заголовка (<svg> або <?xml>),
    а не просто має розширення .svg.

    Алгоритм:
      1. Зчитуємо перші 1024 байти файлу (заголовок)
      2. Декодуємо в UTF-8 (SVG — це XML, тобто текстовий формат)
      3. Шукаємо маркери "<svg" або "<?xml" у заголовку
      4. Повертаємо курсор файлу на початок (seek(0)) — це КРИТИЧНО!
         Без seek(0) Django не зможе зберегти файл, бо курсор
         залишиться в кінці прочитаного фрагмента.

    Args:
        file: Завантажений файл (UploadedFile від Django).

    Raises:
        ValidationError: If the file content is not valid SVG.

    Example::

        from django.core.files.uploadedfile import SimpleUploadedFile

        svg = SimpleUploadedFile("ok.svg", b"<svg><rect/></svg>")
        validate_svg_content(svg)  # OK — не кидає виключення

        png = SimpleUploadedFile("fake.svg", b"not-svg-content")
        validate_svg_content(png)  # ValidationError!

    """
    # --- Крок 1: Зчитуємо заголовок файлу --- #
    # file.seek(0) — переміщуємо курсор на початок файлу.
    # Це важливо, бо файл міг бути частково прочитаний раніше
    # (наприклад, іншим валідатором або Django internals).
    file.seek(0)
    # Читаємо перші 1024 байти — достатньо для визначення формату.
    # SVG починається з <svg> або <?xml version="1.0"?><svg>,
    # тому 1024 байтів завжди вистачить для заголовка.
    raw_header = file.read(1024)

    # --- Крок 2: Повертаємо курсор на початок --- #
    # КРИТИЧНО! Без цього Django не зможе зберегти файл на диск,
    # бо курсор залишиться після 1024-го байту.
    file.seek(0)

    # --- Крок 3: Декодуємо та перевіряємо вміст --- #
    # SVG — це XML (текстовий формат), тому декодуємо в UTF-8.
    # errors="ignore" — ігноруємо байти, що не є валідним UTF-8
    # (бінарні файли типу PNG будуть декодовані з "мусором", але без помилки).
    header = raw_header.decode("utf-8", errors="ignore").strip().lower()

    # Перевіряємо наявність SVG-маркерів:
    # - "<svg" — стандартний початок SVG-документа
    # - "<?xml" — XML-декларація, що часто передує <svg>
    is_svg = "<svg" in header or header.startswith("<?xml")

    if not is_svg:
        # --- Крок 4: Піднімаємо ValidationError --- #
        # ValidationError — стандартний виняток Django для помилок валідації.
        # message — текст помилки, що відображається користувачу.
        # code — ідентифікатор помилки для програмної обробки.
        # Документація:
        #   https://docs.djangoproject.com/en/stable/ref/exceptions/#validationerror
        raise ValidationError(
            _("Файл не є валідним SVG. Завантажте файл у форматі SVG."),
            code="invalid_svg",
        )
