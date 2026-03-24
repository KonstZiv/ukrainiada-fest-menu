# ---------------------------------------------------------------------------
# forms.py — Форми застосунку menu
#
# Django Forms — механізм для створення, валідації та обробки HTML-форм.
# ModelForm — форма, що автоматично генерується з моделі:
#   - Поля форми створюються з полів моделі
#   - Валідація базується на обмеженнях моделі (max_length, required тощо)
#   - form.save() автоматично створює або оновлює об'єкт у БД
#
# Документація:
#   https://docs.djangoproject.com/en/stable/topics/forms/
#   https://docs.djangoproject.com/en/stable/topics/forms/modelforms/
# ---------------------------------------------------------------------------

from typing import Any

from django import forms
from django.db import models
from django.forms import BaseInlineFormSet
from django.utils.translation import gettext_lazy as _

from menu.models import (
    Category,
    CategoryLogo,
    Dish,
    DishMainImage,
    DishPicture,
    Tag,
    TagLogo,
)


class CategoryForm(forms.ModelForm):
    """Form for creating and updating Category objects.

    ModelForm автоматично створює поля з моделі Category.
    Ми лише вказуємо які поля включити (fields) та кастомні widgets
    для стилізації під Bootstrap.

    Attributes:
        Meta.model: Category — модель, на основі якої будується форма.
        Meta.fields: List of model fields to include in the form.
        Meta.widgets: Custom widget overrides for Bootstrap styling.

    """

    class Meta:
        # model — модель, з якої генеруються поля форми.
        model = Category
        # fields — які поля моделі включити у форму.
        # Рекомендується явно вказувати поля (а не __all__),
        # щоб випадково не показати службові поля.
        fields = ["title", "description", "number_in_line"]
        # widgets — словник {field_name: Widget} для кастомізації HTML-елементів.
        # form-control — Bootstrap клас для стилізації <input> та <textarea>.
        # Документація widgets:
        #   https://docs.djangoproject.com/en/stable/ref/forms/widgets/
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "number_in_line": forms.NumberInput(attrs={"class": "form-control"}),
        }


# ---------------------------------------------------------------------------
# CategoryLogoForm — форма завантаження логотипу категорії (таска 2.3)
#
# Це ДРУГА форма, яка обробляється в тому самому view (category_create).
# Дві Django-форми → одна HTML-форма у шаблоні.
#
# Ключові концепції:
#   - request.FILES — Django розділяє текстові дані (POST) та файли (FILES)
#   - enctype="multipart/form-data" — без цього атрибуту файли НЕ передаються
#   - prefix — дозволяє уникнути конфлікту імен полів між формами
#     (обидві мають поле "title", prefix додає префікс: "logo-title")
#
# Документація file uploads:
#   https://docs.djangoproject.com/en/stable/topics/http/file-uploads/
# Документація prefix:
#   https://docs.djangoproject.com/en/stable/ref/forms/api/#prefixes-for-forms
# ---------------------------------------------------------------------------
class CategoryLogoForm(forms.ModelForm):
    """Form for uploading a category logo (SVG file).

    Використовується як додаткова (inline) форма поряд з CategoryForm.
    Prefix "logo" запобігає конфлікту полів: CategoryForm.title vs
    CategoryLogoForm.title стають "title" та "logo-title" у HTML.

    Attributes:
        Meta.model: CategoryLogo — модель логотипу.
        Meta.fields: title (назва логотипу) та image (SVG-файл).

    """

    class Meta:
        model = CategoryLogo
        # fields — лише title та image.
        # Поле category НЕ включаємо — його ми зв'язуємо вручну у view
        # через save(commit=False) + logo.category = category.
        fields = ["title", "image"]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Назва логотипу")}
            ),
            # FileInput — стандартний HTML <input type="file">.
            # accept=".svg" — підказка для браузера (фільтрує файли у діалозі),
            # але НЕ замінює серверну валідацію! Користувач може обійти accept.
            # Документація:
            #   https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input/file#accept
            "image": forms.FileInput(attrs={"class": "form-control", "accept": ".svg"}),
        }


class TagForm(forms.ModelForm):
    """Form for creating and updating Tag objects.

    Аналогічна CategoryForm, але для моделі Tag.
    Tag має лише два поля: title та description.

    Порівняння з CategoryForm (таска 2.1):
    - CategoryForm → FBV (category_create) — ручна обробка GET/POST
    - TagForm → CBV (TagCreateView) — Django робить все автоматично

    Attributes:
        Meta.model: Tag — модель, на основі якої будується форма.
        Meta.fields: List of model fields to include in the form.
        Meta.widgets: Custom widget overrides for Bootstrap styling.

    """

    class Meta:
        model = Tag
        # Tag має лише title (з ModelWithTitle) та description.
        # На відміну від Category, тут немає number_in_line.
        fields = ["title", "description"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


# ---------------------------------------------------------------------------
# TagLogoForm — форма завантаження логотипу тега (таска 2.5)
#
# Закріплення патерну з CategoryLogoForm (таска 2.3):
#   - Та сама структура: ModelForm для Logo-моделі з полями title + image
#   - Той самий prefix ("logo") для уникнення конфлікту імен полів
#   - Той самий validate_svg_content валідатор (DRY — один валідатор, дві моделі)
#
# Різниця з CategoryLogoForm:
#   - model = TagLogo (замість CategoryLogo)
#   - Використовується у CBV (TagCreateView) замість FBV (category_create)
#   - CBV потребує перевизначення get_context_data() та form_valid()
#
# Документація:
#   https://docs.djangoproject.com/en/stable/topics/forms/modelforms/
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# DishForm — форма створення/редагування страви (таска 2.6)
#
# Найскладніша форма у спринті — поєднує всі типи зв'язків:
#   1. ForeignKey (category) — dropdown <select> для вибору категорії
#   2. ManyToManyField (tags) — множинний вибір через checkboxes
#   3. Звичайні поля — title, description, price, weight, calorie
#
# Нові концепції:
#   - forms.Select — HTML <select> для FK. Django автоматично заповнює
#     options із Category.objects.all(). class="form-select" — Bootstrap стиль.
#     Документація:
#       https://docs.djangoproject.com/en/stable/ref/forms/widgets/#select
#
#   - forms.CheckboxSelectMultiple — замість стандартного <select multiple>
#     рендерить кожен тег як окремий <input type="checkbox">.
#     Зручніше для користувача, особливо при невеликій кількості варіантів.
#     Django автоматично обробляє збереження M2M зв'язків через form.save().
#     Документація:
#       https://docs.djangoproject.com/en/stable/ref/forms/widgets/#checkboxselectmultiple
#
#   - M2M + form.save() — для ManyToManyField Django викликає form.save_m2m()
#     автоматично (якщо commit=True). При commit=False потрібно вручну:
#       obj = form.save(commit=False)
#       obj.save()
#       form.save_m2m()  # ← зберігає M2M зв'язки
#     Документація:
#       https://docs.djangoproject.com/en/stable/topics/forms/modelforms/#the-save-method
# ---------------------------------------------------------------------------
class DishForm(forms.ModelForm):
    """Form for creating and updating Dish objects.

    Combines FK dropdown (category), M2M checkboxes (tags),
    and standard text/number fields in a single form.

    Attributes:
        Meta.model: Dish — модель, на основі якої будується форма.
        Meta.fields: All user-editable fields of the Dish model.
        Meta.widgets: Custom widget overrides for Bootstrap styling.

    """

    class Meta:
        model = Dish
        # fields — усі поля, які користувач заповнює при створенні страви.
        # Поля id та зворотні зв'язки (main_image, additional_images)
        # НЕ включаємо — вони керуються окремо.
        fields = [
            "title",
            "description",
            "price",
            "weight",
            "calorie",
            "category",
            "tags",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            # DecimalField → NumberInput. step="0.01" дозволяє вводити центи (€11.50).
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "weight": forms.NumberInput(attrs={"class": "form-control"}),
            "calorie": forms.NumberInput(attrs={"class": "form-control"}),
            # --- FK: Select widget --- #
            # forms.Select — стандартний HTML <select> з варіантами.
            # Django автоматично заповнює <option> із Category.objects.all().
            # form-select — Bootstrap клас для стилізації <select>.
            # Документація:
            #   https://docs.djangoproject.com/en/stable/ref/forms/widgets/#select
            "category": forms.Select(attrs={"class": "form-select"}),
            # --- M2M: CheckboxSelectMultiple widget --- #
            # Замість <select multiple> (де треба тримати Ctrl для вибору кількох)
            # рендеримо кожен тег як окремий checkbox — зручніше для користувача.
            # Django автоматично обробляє список обраних id і зберігає M2M зв'язки.
            # Документація:
            #   https://docs.djangoproject.com/en/stable/ref/forms/widgets/#checkboxselectmultiple
            "tags": forms.CheckboxSelectMultiple(),
        }

    # --- Кастомна валідація поля tags (таска 2.6.1) --- #
    # clean_<fieldname>() — метод валідації конкретного поля.
    # Django викликає його автоматично після базової валідації поля.
    # Ланцюжок валідації:
    #   1. Поле self.fields["tags"].clean(value) — базова валідація (типи, існування)
    #   2. self.clean_tags() — кастомна валідація (наша бізнес-логіка)
    #   3. self.clean() — валідація між полями (якщо потрібна)
    #
    # tags має blank=True у моделі (Django дозволяє порожній M2M),
    # але ми хочемо вимагати хоча б один тег на рівні форми.
    #
    # Документація:
    #   https://docs.djangoproject.com/en/stable/ref/forms/validation/#cleaning-a-specific-field-attribute
    def clean_tags(self) -> models.QuerySet[Tag]:
        """Validate that at least one tag is selected.

        Raises:
            ValidationError: If no tags are selected.

        Returns:
            QuerySet of selected Tag objects.

        """
        tags: models.QuerySet[Tag, Tag] | None = self.cleaned_data.get("tags")
        if not tags:
            raise forms.ValidationError(_("Оберіть хоча б один тег для страви."))
        return tags


# ---------------------------------------------------------------------------
# DishMainImageForm — форма завантаження головного зображення страви (таска 2.6)
#
# Аналогічна CategoryLogoForm / TagLogoForm, але з важливою різницею:
#   - ImageField замість FileField — Django перевіряє що файл є зображенням
#     (використовує Pillow для визначення формату: JPEG, PNG, WebP тощо).
#   - accept="image/*" — підказка для браузера, фільтрує діалог вибору файлу.
#
# Порівняння FileField vs ImageField:
#   FileField — приймає будь-який файл (ми додавали SVG-валідатор вручну)
#   ImageField — приймає лише зображення (Pillow валідує автоматично)
#   Документація:
#     https://docs.djangoproject.com/en/stable/ref/models/fields/#imagefield
#
# Патерн використання — той самий "inline form" що й для логотипів:
#   1. prefix="main_image" — розділяє поля від DishForm
#   2. save(commit=False) — створює об'єкт без збереження
#   3. image.dish = dish — зв'язуємо вручну
#   4. image.save() — зберігаємо у БД
# ---------------------------------------------------------------------------
class DishMainImageForm(forms.ModelForm):
    """Form for uploading the main dish image (JPEG/PNG/WebP).

    Використовується як додаткова (inline) форма поряд з DishForm.
    На відміну від CategoryLogoForm (SVG/FileField), тут ImageField —
    Django + Pillow автоматично перевіряють що файл є зображенням.

    Attributes:
        Meta.model: DishMainImage — модель головного зображення.
        Meta.fields: title (назва зображення) та image (файл зображення).

    """

    class Meta:
        model = DishMainImage
        # Поле dish НЕ включаємо — зв'язуємо вручну через save(commit=False).
        fields = ["title", "image"]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Назва зображення")}
            ),
            # accept="image/*" — підказка для браузера: показувати лише зображення
            # у діалозі вибору файлу. НЕ замінює серверну валідацію!
            # Документація:
            #   https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input/file#accept
            "image": forms.FileInput(
                attrs={"class": "form-control", "accept": "image/*"}
            ),
        }


class TagLogoForm(forms.ModelForm):
    """Form for uploading a tag logo (SVG file).

    Використовується як додаткова (inline) форма поряд з TagForm у CBV.
    Аналогічна CategoryLogoForm, але для моделі TagLogo.

    Attributes:
        Meta.model: TagLogo — модель логотипу тега.
        Meta.fields: title (назва логотипу) та image (SVG-файл).

    """

    class Meta:
        model = TagLogo
        # Поле tag НЕ включаємо — зв'язуємо вручну через save(commit=False).
        fields = ["title", "image"]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Назва логотипу")}
            ),
            "image": forms.FileInput(attrs={"class": "form-control", "accept": ".svg"}),
        }


# ---------------------------------------------------------------------------
# DishPictureFormSet — formset для додаткових зображень страви (таска 2.6.1)
#
# FormSet — це набір однакових форм, що обробляються разом.
# inlineformset_factory — фабрична функція, що створює FormSet
# для дочірньої моделі (DishPicture), прив'язаної до батьківської (Dish).
#
# Як це працює:
#   1. Django генерує N однакових форм (кожна = один DishPicture)
#   2. ManagementForm — приховані поля (TOTAL_FORMS, INITIAL_FORMS),
#      що повідомляють Django скільки форм очікувати при POST
#   3. Кожна форма має prefix з індексом: "pictures-0-title", "pictures-1-title"
#   4. formset.save() зберігає всі заповнені форми, пропускаючи порожні
#
# Параметри:
#   parent_model: Dish — батьківська модель (FK у DishPicture.dish)
#   model: DishPicture — дочірня модель
#   fields: які поля показувати (title, image)
#   extra: скільки порожніх форм показувати за замовчуванням
#   can_delete: False — при створенні видаляти нічого
#
# Документація:
#   https://docs.djangoproject.com/en/stable/topics/forms/formsets/
#   https://docs.djangoproject.com/en/stable/topics/forms/modelforms/#inline-formsets
# ---------------------------------------------------------------------------
DishPictureFormSet: type[BaseInlineFormSet[Any, Any, Any]] = (
    forms.inlineformset_factory(
        Dish,
        DishPicture,
        fields=["title", "image"],
        extra=1,
        can_delete=False,
        widgets={
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Назва зображення")}
            ),
            "image": forms.FileInput(
                attrs={"class": "form-control", "accept": "image/*"}
            ),
        },
    )
)
