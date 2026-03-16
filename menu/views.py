# ---------------------------------------------------------------------------
# views.py — Представлення (views) застосунку menu
#
# Views отримують HTTP-запит, обробляють дані і повертають HTTP-відповідь.
# Використовуємо:
#   - Function-Based Views (FBV) — для index, category_list, dish_list, dish_detail
#   - Class-Based Views (CBV) — generic ListView для tag_list (таска 1.8)
#
# Документація Django Views:
#   https://docs.djangoproject.com/en/stable/topics/http/views/
# Документація Generic Views:
#   https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-display/
# ---------------------------------------------------------------------------

from django.contrib.auth.models import AnonymousUser
from django.db import models, transaction
from django.db.models import Prefetch, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import generic

from menu.forms import (
    CategoryForm,
    CategoryLogoForm,
    DishForm,
    DishMainImageForm,
    DishPictureFormSet,
    TagForm,
    TagLogoForm,
)
from menu.models import Category, Dish, Tag
from user.models import User
from user.roles import is_kitchen_staff, is_management, is_waiter_staff

_AnyUser = User | AnonymousUser


def _can_see_all_dishes(user: _AnyUser) -> bool:
    """Staff and authenticated non-visitors can see OUT-of-stock dishes."""
    if not isinstance(user, User):
        return False
    return is_management(user) or is_kitchen_staff(user) or is_waiter_staff(user)


def index(request: HttpRequest) -> HttpResponse:
    """Головна сторінка /menu/ — знайомство з рестораном.

    Контекст:
    - slides: список слайдів для Bootstrap Carousel (зображення, заголовок, текст)
    - cat_num: кількість категорій у меню
    - tag_num: кількість тегів
    - dish_num: кількість страв

    Зображення — безкоштовні фото з Unsplash (ліцензія дозволяє вільне використання).
    Формат URL: https://images.unsplash.com/photo-{ID}?w=800&h=400&fit=crop
    Параметри w, h, fit — серверна обрізка Unsplash (CDN), без навантаження на клієнт.

    Документація Bootstrap Carousel:
      https://getbootstrap.com/docs/5.3/components/carousel/
    """
    # --- Слайди для каруселі --- #
    # Кожен слайд — словник з image, title, text.
    # Фото з Unsplash CDN — стабільні URL, безкоштовна ліцензія.
    # Параметри URL:
    #   w=800&h=500  — пропорція ~16:10 (більше висоти, щоб обличчя не обрізались)
    #   fit=crop     — обрізка під заданий розмір без спотворення
    #   crop=entropy — «розумний» кроп: Unsplash фокусується на найцікавішій частині
    slides = [
        {
            "image": "https://images.unsplash.com/photo-1534308983496-4fabb1a015ee?w=800&h=500&fit=crop&crop=entropy",
            "title": "Ласкаво просимо",
            "text": "Середземноморська та балканська кухня на березі Адріатики.",
        },
        {
            "image": "https://images.unsplash.com/photo-1577219491135-ce391730fb2c?w=800&h=500&fit=crop&crop=entropy",
            "title": "Наша команда шеф-кухарів",
            "text": "Майстри з 20-річним досвідом готують для вас найкраще.",
        },
        {
            "image": "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=800&h=500&fit=crop&crop=entropy",
            "title": "Атмосфера Jadran Sun",
            "text": "Ваш комфорт — наш пріоритет.",
        },
    ]

    # --- Статистика меню --- #
    cat_num = Category.objects.count()
    tag_num = Tag.objects.count()
    dish_num = Dish.objects.count()

    return render(
        request,
        "menu/index.html",
        context={
            "slides": slides,
            "cat_num": cat_num,
            "tag_num": tag_num,
            "dish_num": dish_num,
        },
    )


def category_list(request: HttpRequest) -> HttpResponse:
    """Список категорій /menu/categories/ — accordion з вкладеними стравами.

    Кожна категорія розкривається у список страв (назва, опис, ціна, теги).
    Перша категорія розкрита за замовчуванням, решта — закриті.

    Контекст:
    - categories: QuerySet усіх категорій

    Оптимізація (таска 1.6):
    - prefetch_related("dishes") — завантажує всі страви одним запитом
      замість окремого запиту для кожної категорії (N+1 → 2 запити).
    - Prefetch("dishes", queryset=Dish.objects.prefetch_related("tags"))
      — додатково завантажує теги страв ще одним запитом (разом: 3 запити).
    - Без оптимізації було: 1 (categories) + N (dishes) + N*M (tags) запитів.

    Документація prefetch_related:
      https://docs.djangoproject.com/en/stable/ref/models/querysets/#prefetch-related
    Документація Prefetch object:
      https://docs.djangoproject.com/en/stable/ref/models/querysets/#django.db.models.Prefetch
    Документація Bootstrap Accordion:
      https://getbootstrap.com/docs/5.3/components/collapse/#accordion
    """
    # --- Оптимізований QuerySet (таска 1.6) --- #
    # Prefetch("dishes", queryset=...) — дозволяє задати кастомний queryset
    # для зв'язку. Тут ми додаємо prefetch_related("tags") до кожної страви,
    # щоб теги також завантажились одним запитом.
    # Результат: 3 SQL-запити замість 1 + N + N*M.
    # select_related("logo") — JOIN для OneToOne зв'язку CategoryLogo.
    # prefetch_related("dishes") — окремий запит для ForeignKey (зворотній).
    # Prefetch("dishes", queryset=...) — вкладений prefetch для тегів страв.
    dish_qs = Dish.objects.prefetch_related(
        Prefetch("tags", queryset=Tag.objects.select_related("logo")),  # type: ignore[arg-type]
        "allergens",
    )
    if not _can_see_all_dishes(request.user):
        dish_qs = dish_qs.exclude(availability=Dish.Availability.OUT)
    categories = (
        Category.objects.select_related("logo")
        .prefetch_related(Prefetch("dishes", queryset=dish_qs))
        .all()
    )
    return render(
        request,
        "menu/category_list.html",
        context={"categories": categories},
    )


def category_create(request: HttpRequest) -> HttpResponse:
    """Create a new category with optional logo via FBV.

    Розширення таски 2.1 (таска 2.3): додаємо ДРУГУ форму (CategoryLogoForm)
    для завантаження SVG-логотипу разом зі створенням категорії.

    Дві Django-форми обробляються в одному view, але рендеряться
    в одній HTML-формі у шаблоні. Ключові концепції:

    1. **request.FILES** — Django розділяє текстові дані та файли:
       - request.POST — текстові поля (title, description, number_in_line)
       - request.FILES — завантажені файли (image)
       Документація: https://docs.djangoproject.com/en/stable/topics/http/file-uploads/

    2. **prefix** — коли дві форми мають однакові імена полів (обидві мають "title"),
       prefix додає префікс до HTML-імен: "title" → "logo-title".
       Без prefix Django не розрізнить яке "title" до якої форми належить.
       Документація: https://docs.djangoproject.com/en/stable/ref/forms/api/#prefixes-for-forms

    3. **save(commit=False)** — створює Python-об'єкт БЕЗ збереження у БД,
       щоб ми могли вручну задати logo.category перед збереженням.
       Документація: https://docs.djangoproject.com/en/stable/topics/forms/modelforms/#the-save-method

    4. **enctype="multipart/form-data"** — обов'язковий атрибут <form> для файлів.
       Без нього request.FILES буде порожнім!
       Документація: https://docs.djangoproject.com/en/stable/topics/http/file-uploads/#basic-file-uploads
    """
    if request.method == "POST":
        # --- Обробка POST-запиту з двома формами --- #
        # CategoryForm отримує лише request.POST (текстові дані).
        form = CategoryForm(request.POST)
        # CategoryLogoForm отримує і POST, і FILES.
        # prefix="logo" — всі поля цієї форми мають HTML-імена "logo-title", "logo-image".
        # Це запобігає конфлікту з CategoryForm.title.
        logo_form = CategoryLogoForm(request.POST, request.FILES, prefix="logo")

        # --- Валідація обох форм --- #
        # Перевіряємо основну форму завжди.
        # Логотип — опціональний: якщо файл не завантажено, пропускаємо logo_form.
        # has_logo — перевіряємо чи користувач завантажив файл.
        has_logo = bool(request.FILES.get("logo-image"))

        if form.is_valid() and (not has_logo or logo_form.is_valid()):
            # form.save() — створює Category у БД, повертає створений об'єкт.
            category = form.save()

            if has_logo:
                # save(commit=False) — створює об'єкт CategoryLogo в пам'яті,
                # але НЕ зберігає у БД. Це дозволяє вручну задати поле category.
                logo = logo_form.save(commit=False)
                # Зв'язуємо логотип з щойно створеною категорією.
                logo.category = category
                # Тепер зберігаємо у БД (з правильним FK).
                logo.save()

            return redirect("menu:category_list")
    else:
        # --- Обробка GET-запиту --- #
        form = CategoryForm()
        # prefix="logo" — і для GET, щоб HTML-імена полів співпадали з POST.
        logo_form = CategoryLogoForm(prefix="logo")

    # Якщо GET або POST з помилками — рендеримо шаблон з ОБОМА формами.
    return render(
        request,
        "menu/category_form.html",
        context={"form": form, "logo_form": logo_form},
    )


# ---------------------------------------------------------------------------
# category_update — редагування категорії з логотипом через FBV (таска 2.7)
#
# Аналогічно до category_create, але для UPDATE:
#   1. Завантажуємо існуючий об'єкт: get_object_or_404(Category, pk=pk)
#   2. Передаємо instance=category у CategoryForm — форма заповниться даними
#   3. form.save() викликає UPDATE замість INSERT (бо instance.pk існує)
#
# Для логотипу (OneToOne):
#   - Якщо категорія вже має логотип → instance=existing_logo (UPDATE)
#   - Якщо категорія не має логотипу → порожня форма (INSERT)
#   - Якщо користувач не завантажує файл → логотип залишається без змін
#
# Порівняння з TagUpdateView (CBV):
#   FBV: ручний if/else, render(), повний контроль
#   CBV: перевизначення get_context_data(), form_valid(), менше коду
#   Обидва підходи — валідні, вибір залежить від складності та уподобань.
#
# Документація:
#   https://docs.djangoproject.com/en/stable/topics/http/shortcuts/#get-object-or-404
# ---------------------------------------------------------------------------
def category_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Update an existing category with optional logo via FBV.

    FBV-підхід до edit — аналогічний category_create, але з instance.
    Перевикористовує шаблон category_form.html (підтримує create/update).

    Args:
        request: HTTP request object.
        pk: Primary key of the category to edit.

    """
    # --- Завантажуємо існуючий об'єкт --- #
    # get_object_or_404 — повертає 404 якщо об'єкт не знайдено.
    # select_related("logo") — JOIN для OneToOne, уникаємо зайвого запиту.
    category: Category = get_object_or_404(
        Category.objects.select_related("logo"), pk=pk
    )

    # --- Перевіряємо чи категорія вже має логотип --- #
    existing_logo = getattr(category, "logo", None)

    if request.method == "POST":
        # instance=category — форма заповниться поточними даними,
        # form.save() зробить UPDATE замість INSERT.
        form = CategoryForm(request.POST, instance=category)
        logo_form = CategoryLogoForm(
            request.POST,
            request.FILES,
            prefix="logo",
            instance=existing_logo,
        )

        has_logo = bool(request.FILES.get("logo-image"))

        if form.is_valid() and (not has_logo or logo_form.is_valid()):
            category = form.save()

            if has_logo:
                logo = logo_form.save(commit=False)
                logo.category = category
                logo.save()

            return redirect("menu:category_list")
    else:
        # --- GET: форма з поточними даними --- #
        form = CategoryForm(instance=category)
        logo_form = CategoryLogoForm(prefix="logo", instance=existing_logo)

    return render(
        request,
        "menu/category_form.html",
        context={"form": form, "logo_form": logo_form},
    )


# ---------------------------------------------------------------------------
# CategoryDeleteView — видалення категорії через generic DeleteView (таска 2.7)
#
# Категорія — батьківський об'єкт для страв (FK CASCADE), тому при видаленні
# каскадно видаляються ВСІ пов'язані об'єкти:
#   - CategoryLogo (OneToOne, CASCADE)
#   - Dish (ForeignKey, CASCADE) — кожна страва у цій категорії
#   - DishMainImage (OneToOne на Dish, CASCADE) — зображення кожної страви
#   - DishPicture (ForeignKey на Dish, CASCADE) — додаткові зображення
#   - Dish.tags M2M записи — зв'язки зі стравами у проміжній таблиці
#
# Це НЕБЕЗПЕЧНА операція — тому на сторінці підтвердження показуємо
# повний список страв, які будуть видалені разом з категорією.
#
# get_context_data() — додаємо dishes у контекст для відображення у шаблоні.
#
# Документація:
#   https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-editing/#deleteview
# ---------------------------------------------------------------------------
class CategoryDeleteView(generic.DeleteView):
    """Delete a category with confirmation showing related dishes.

    GET shows confirmation page with list of dishes that will be deleted.
    POST deletes the category and all related objects (CASCADE).

    Attributes:
        model: Category — модель, яку видаляємо.
        template_name: Path to the confirmation template.
        success_url: URL для redirect після видалення.
        context_object_name: Name of the variable in the template context.

    """

    model = Category
    template_name = "menu/category_confirm_delete.html"
    success_url = reverse_lazy("menu:category_list")
    context_object_name = "category"

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        """Add related dishes to context for display on confirmation page.

        Показуємо список страв, щоб користувач розумів наслідки видалення.
        """
        context = super().get_context_data(**kwargs)
        # Prefetch пов'язані страви для відображення на сторінці підтвердження
        context["dishes"] = self.object.dishes.all()
        return context


def dish_list(request: HttpRequest) -> HttpResponse:
    """Список всіх страв /menu/dishes/."""
    dishes = Dish.objects.select_related("category__logo").prefetch_related(
        "tags__logo", "allergens"
    )
    if not _can_see_all_dishes(request.user):
        dishes = dishes.exclude(availability=Dish.Availability.OUT)
    return render(request, "menu/dish_list.html", context={"dishes": dishes})


def dish_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Деталі конкретної страви /menu/dishes/<pk>/.

    Показує повну інформацію: назва, опис, ціна, вага, калорійність,
    категорія, теги, головне зображення та додаткові фото.

    Оптимізація запитів (таска 1.9):
    - select_related("category", "main_image") — JOIN для FK та OneToOne
      (1 запит замість 3).
    - prefetch_related("tags", "additional_images") — 2 окремі запити
      для M2M та reverse FK.
    Разом: 3 SQL-запити.

    Документація get_object_or_404:
      https://docs.djangoproject.com/en/stable/topics/http/shortcuts/#get-object-or-404
    Документація select_related:
      https://docs.djangoproject.com/en/stable/ref/models/querysets/#select-related
    """
    # --- Оптимізований запит (таска 1.9) --- #
    # get_object_or_404 приймає QuerySet або Model.
    # Передаємо QuerySet з select_related + prefetch_related,
    # щоб усі зв'язані дані завантажились мінімальною кількістю запитів.
    # select_related — для FK (category) та OneToOne (main_image): JOIN.
    # prefetch_related — для M2M (tags) та reverse FK (additional_images): окремі запити.
    dish: Dish = get_object_or_404(
        Dish.objects.select_related("category", "main_image").prefetch_related(
            "tags__logo", "additional_images"
        ),
        pk=pk,
    )
    return render(request, "menu/dish_detail.html", context={"dish": dish})


# ---------------------------------------------------------------------------
# TagListView — перший Class-Based View (CBV) у проєкті (таска 1.8)
#
# generic.ListView — готовий view для відображення списку об'єктів.
# Замість ручного створення QuerySet і виклику render(), ListView робить це сам.
# Нам залишається лише вказати model, template_name і перевизначити get_queryset().
#
# Порівняння з FBV category_list:
#   FBV — 10+ рядків коду, ручний render()
#   CBV — 5 рядків налаштувань, решту робить Django
#
# Документація:
#   https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-display/#listview
# ---------------------------------------------------------------------------
class TagListView(generic.ListView):
    """List all tags with their dishes grouped by category.

    Each tag expands into a list of dishes, grouped by category using
    ``{% regroup %}`` in the template.

    Attributes:
        model: Tag — the model to list.
        template_name: Path to the template.
        context_object_name: Name of the variable in the template context.

    """

    # model — модель, з якої ListView бере дані.
    # ListView автоматично викликає model.objects.all() (якщо не перевизначити get_queryset).
    model = Tag
    # template_name — шлях до шаблону. За замовчуванням Django шукає
    # <app_name>/<model_name>_list.html (menu/tag_list.html), але ми вказуємо явно.
    template_name = "menu/tag_list.html"
    # context_object_name — ім'я змінної у контексті шаблону.
    # За замовчуванням "object_list", але "tags" — зрозуміліше.
    context_object_name = "tags"

    def get_queryset(self) -> models.QuerySet[Tag]:
        """Return tags with prefetched dishes and their categories.

        Optimized query chain:
          1. Tag.objects.all() — один запит для всіх тегів
          2. Prefetch("dishes") — один запит для всіх страв, пов'язаних з тегами
          3. select_related("category") — JOIN для категорії кожної страви (без N+1)

        Dishes are ordered by category.number_in_line then by title,
        so ``{% regroup %}`` in the template groups them correctly.

        Docs:
          https://docs.djangoproject.com/en/stable/ref/models/querysets/#prefetch-related
        """
        # --- Оптимізований QuerySet --- #
        # Prefetch("dishes", queryset=...) — вкладений prefetch з кастомним queryset.
        # select_related("category") — JOIN для FK (один запит замість N).
        # order_by("category__number_in_line", "title") — сортування для {% regroup %}:
        #   {% regroup %} працює коректно ТІЛЬКИ якщо дані вже відсортовані по полю групування.
        #   Документація: https://docs.djangoproject.com/en/stable/ref/templates/builtins/#regroup
        return (
            Tag.objects.select_related("logo")
            .prefetch_related(
                Prefetch(
                    "dishes",
                    queryset=Dish.objects.select_related("category").order_by(
                        "category__number_in_line", "title"
                    ),
                )
            )
            .order_by("title")
        )


# ---------------------------------------------------------------------------
# TagCreateView — створення тега з логотипом через generic CreateView
# (таски 2.2 + 2.5)
#
# Порівняння з FBV category_create (таска 2.3):
#   FBV — ручна обробка: if request.method == "POST", form.is_valid(), render()
#   CBV — перевизначення методів: get_context_data(), form_valid()
#
# Для роботи з ДРУГОЮ формою (TagLogoForm) у CBV потрібно перевизначити:
#   1. get_context_data() — додати logo_form у контекст шаблону
#   2. form_valid() — обробити logo_form при успішній валідації TagForm
#
# Порівняння реалізації двох форм:
#   FBV (category_create):
#     - Обидві форми створюються вручну в тілі функції
#     - Повний контроль над потоком виконання
#   CBV (TagCreateView):
#     - Основна форма (TagForm) обробляється Django автоматично
#     - Додаткова форма (TagLogoForm) — через перевизначення методів
#     - Менше коду, але потрібно розуміти lifecycle CBV
#
# Документація:
#   https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-editing/#createview
#   https://docs.djangoproject.com/en/stable/ref/class-based-views/mixins-editing/#formmixin
# ---------------------------------------------------------------------------
class TagCreateView(generic.CreateView):
    """Create a new tag with optional logo via generic CreateView.

    Закріплення патерну "дві форми в одному view" (таска 2.5):
    - Основна форма (TagForm) обробляється стандартним CreateView
    - Додаткова (TagLogoForm) — через перевизначення get_context_data/form_valid

    Порівняння з FBV category_create:
      FBV: if/else + ручний render() — повний контроль, більше коду
      CBV: перевизначення методів — менше коду, але потрібно знати lifecycle

    Attributes:
        model: Tag — модель, для якої створюється об'єкт.
        form_class: TagForm — клас основної форми.
        template_name: Path to the form template.
        success_url: URL для redirect після збереження.

    """

    model = Tag
    form_class = TagForm
    template_name = "menu/tag_form.html"
    success_url = reverse_lazy("menu:tag_list")

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        """Add TagLogoForm to the template context.

        get_context_data() — метод CBV, що формує словник контексту для шаблону.
        За замовчуванням CreateView додає лише основну форму ("form").
        Ми додаємо logo_form, щоб шаблон міг рендерити обидві форми.

        Порівняння з FBV:
          FBV: logo_form створюється вручну і передається в render()
          CBV: logo_form додається через super().get_context_data()

        Документація:
          https://docs.djangoproject.com/en/stable/ref/class-based-views/mixins-simple/#contextmixin
        """
        context = super().get_context_data(**kwargs)
        # Додаємо logo_form у контекст, тільки якщо його ще немає.
        # При POST з помилками form_valid/form_invalid може вже додати logo_form.
        if "logo_form" not in context:
            context["logo_form"] = TagLogoForm(prefix="logo")
        return context

    def form_valid(self, form: TagForm) -> HttpResponse:
        """Handle valid TagForm + optional TagLogoForm.

        form_valid() викликається Django ПІСЛЯ успішної валідації основної форми.
        Тут ми додаємо обробку другої форми (TagLogoForm):

        1. Створюємо TagLogoForm з request.POST + request.FILES
        2. Перевіряємо чи користувач завантажив файл (has_logo)
        3. Якщо завантажив — валідуємо logo_form
        4. Зберігаємо Tag, потім TagLogo з tag=щойно_створений_тег

        Порівняння з FBV category_create:
          FBV: весь цей код знаходиться в if request.method == "POST" блоці
          CBV: тільки додаткова логіка — основну форму Django обробив сам

        Документація:
          https://docs.djangoproject.com/en/stable/ref/class-based-views/mixins-editing/#django.views.generic.edit.FormMixin.form_valid
        """
        # --- Створюємо форму логотипу з даними запиту --- #
        # prefix="logo" — HTML-імена: "logo-title", "logo-image"
        logo_form = TagLogoForm(self.request.POST, self.request.FILES, prefix="logo")

        # --- Перевіряємо чи користувач завантажив файл --- #
        has_logo = bool(self.request.FILES.get("logo-image"))

        if has_logo and not logo_form.is_valid():
            # Логотип завантажено, але він невалідний (наприклад, не SVG).
            # Повертаємо форму з помилками — передаємо logo_form у контекст.
            return self.render_to_response(
                self.get_context_data(form=form, logo_form=logo_form)
            )

        # --- Зберігаємо Tag --- #
        # form.save() — створює Tag у БД, повертає об'єкт.
        tag = form.save()

        # --- Зберігаємо TagLogo (якщо файл завантажено) --- #
        if has_logo:
            # save(commit=False) — створює TagLogo в пам'яті без збереження в БД.
            # Це дозволяє вручну задати tag= перед збереженням.
            logo = logo_form.save(commit=False)
            logo.tag = tag
            logo.save()

        return redirect(self.success_url)


# ---------------------------------------------------------------------------
# TagUpdateView — редагування тега з логотипом через generic UpdateView
# (таска 2.7)
#
# UpdateView — generic view для редагування існуючого об'єкта.
# Працює майже ідентично до CreateView, але:
#   1. Django завантажує існуючий об'єкт з БД по pk з URL
#   2. Форма заповнюється поточними даними (instance=tag)
#   3. form.save() оновлює (UPDATE) замість створення (INSERT)
#
# Для логотипу при update є додаткова логіка:
#   - Якщо тег вже має логотип — показуємо форму з instance=existing_logo
#   - Якщо тег не має логотипу — показуємо порожню форму
#   - Користувач може: змінити логотип, додати новий, або залишити без змін
#
# Документація:
#   https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-editing/#updateview
# ---------------------------------------------------------------------------
class TagUpdateView(generic.UpdateView):
    """Update an existing tag with optional logo via generic UpdateView.

    Reuses tag_form.html — the template already supports both create and update
    modes via ``{% if form.instance.pk %}`` checks.

    Attributes:
        model: Tag — модель, яку редагуємо.
        form_class: TagForm — клас основної форми.
        template_name: Path to the form template (shared with TagCreateView).
        success_url: URL для redirect після збереження.

    """

    model = Tag
    form_class = TagForm
    template_name = "menu/tag_form.html"
    success_url = reverse_lazy("menu:tag_list")

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        """Add TagLogoForm to the template context.

        При update, якщо тег вже має логотип, передаємо його як instance
        у TagLogoForm — форма покаже поточні дані (title, поточний файл).
        Якщо логотипу немає — передаємо порожню форму.

        hasattr(tag, "logo") перевіряє існування OneToOne зв'язку.
        При OneToOneField Django створює зворотній зв'язок, але якщо
        пов'язаного об'єкта немає — доступ через tag.logo кине
        RelatedObjectDoesNotExist. Тому використовуємо hasattr().

        Документація:
          https://docs.djangoproject.com/en/stable/ref/models/fields/#onetoonefield
        """
        context = super().get_context_data(**kwargs)
        if "logo_form" not in context:
            tag = self.object
            # --- Перевіряємо чи тег вже має логотип --- #
            # hasattr — безпечна перевірка OneToOne: якщо логотипу немає,
            # tag.logo кидає RelatedObjectDoesNotExist замість повернення None.
            if hasattr(tag, "logo"):
                # instance=tag.logo — форма заповниться поточними даними логотипу
                context["logo_form"] = TagLogoForm(instance=tag.logo, prefix="logo")
            else:
                context["logo_form"] = TagLogoForm(prefix="logo")
        return context

    def form_valid(self, form: TagForm) -> HttpResponse:
        """Handle valid TagForm + optional TagLogoForm on update.

        Логіка аналогічна TagCreateView.form_valid(), але з нюансами:
        - Якщо тег вже має логотип і користувач завантажує новий файл —
          передаємо instance=existing_logo, щоб Django оновив (UPDATE)
          існуючий запис замість створення нового.
        - Якщо тег не має логотипу і користувач завантажує файл —
          створюємо новий TagLogo (як при create).

        Документація:
          https://docs.djangoproject.com/en/stable/ref/class-based-views/mixins-editing/#django.views.generic.edit.FormMixin.form_valid
        """
        tag = form.save()

        has_logo = bool(self.request.FILES.get("logo-image"))
        if has_logo:
            # --- Визначаємо чи оновлюємо існуючий чи створюємо новий --- #
            existing_logo = getattr(tag, "logo", None)
            logo_form = TagLogoForm(
                self.request.POST,
                self.request.FILES,
                prefix="logo",
                instance=existing_logo,
            )

            if not logo_form.is_valid():
                return self.render_to_response(
                    self.get_context_data(form=form, logo_form=logo_form)
                )

            logo = logo_form.save(commit=False)
            logo.tag = tag
            logo.save()

        return redirect(self.success_url)


# ---------------------------------------------------------------------------
# TagDeleteView — видалення тега через generic DeleteView (таска 2.7)
#
# DeleteView — generic view для видалення об'єкта з підтвердженням.
# Працює у два етапи:
#   1. GET — показує сторінку підтвердження: "Ви впевнені?"
#   2. POST — видаляє об'єкт і робить redirect
#
# Django автоматично видаляє пов'язані об'єкти через on_delete=CASCADE:
#   - Tag → TagLogo (OneToOne, CASCADE) — логотип видаляється разом з тегом
#   - Tag → Dish.tags (ManyToMany) — зв'язки у проміжній таблиці видаляються,
#     але самі страви залишаються (M2M не CASCADE, а просто видалення зв'язку)
#
# Файли зображень:
#   Django за замовчуванням НЕ видаляє файли з диску при видаленні об'єкта.
#   Для учбового проєкту це прийнятно. У production використовують
#   django-cleanup або сигнал post_delete.
#
# Шаблон:
#   За замовчуванням DeleteView шукає <model>_confirm_delete.html.
#   Ми вказуємо template_name явно для кращого контролю.
#
# Документація:
#   https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-editing/#deleteview
# ---------------------------------------------------------------------------
class TagDeleteView(generic.DeleteView):
    """Delete a tag with confirmation page.

    GET shows confirmation page, POST deletes the tag.
    Related TagLogo is deleted automatically via CASCADE.

    Attributes:
        model: Tag — модель, яку видаляємо.
        template_name: Path to the confirmation template.
        success_url: URL для redirect після видалення.
        context_object_name: Name of the variable in the template context.

    """

    model = Tag
    template_name = "menu/tag_confirm_delete.html"
    success_url = reverse_lazy("menu:tag_list")
    context_object_name = "tag"


# ---------------------------------------------------------------------------
# DishCreateView — створення страви через generic CreateView (таски 2.6, 2.6.1)
#
# Найскладніший view у спринті — поєднує:
#   1. FK (category) — Select widget, Django обробляє автоматично
#   2. M2M (tags) — CheckboxSelectMultiple, мінімум 1 тег (clean_tags)
#   3. Inline form (DishMainImageForm) — ОБОВ'ЯЗКОВЕ головне зображення
#   4. Inline formset (DishPictureFormSet) — довільна кількість додаткових фото
#   5. transaction.atomic() — все або нічого (ACID: Atomicity)
#
# Таска 2.6.1 додає:
#   - Обов'язковість головного зображення (перевірка has_image у form_valid)
#   - clean_tags() у DishForm — мінімум 1 тег
#   - DishPictureFormSet — inlineformset_factory для додаткових зображень
#   - transaction.atomic() — якщо будь-яке збереження падає, все відкочується
#
# Транзакції в Django:
#   За замовчуванням Django загортає кожен запит у транзакцію (ATOMIC_REQUESTS).
#   Але наш view зберігає КІЛЬКА моделей послідовно:
#     Dish → DishMainImage → DishPicture (0..N)
#   Якщо DishPicture.save() падає — Dish і DishMainImage вже в БД (сироти).
#   transaction.atomic() гарантує: або всі INSERT виконаються, або жоден.
#   Документація:
#     https://docs.djangoproject.com/en/stable/topics/db/transactions/
#
# M2M + save(commit=False) + save_m2m():
#   Для ManyToManyField Django потребує id об'єкта (бо M2M = окрема таблиця).
#   При commit=False об'єкт ще не має id → form.save_m2m() зберігає M2M окремо.
#   Документація:
#     https://docs.djangoproject.com/en/stable/topics/forms/modelforms/#the-save-method
#
# Документація CreateView:
#   https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-editing/#createview
# ---------------------------------------------------------------------------
class DishCreateView(generic.CreateView):
    """Create a new dish with main image, optional extra images, via CreateView.

    Найскладніший випадок форми: FK dropdown (category),
    M2M checkboxes (tags, мінімум 1), обов'язкове головне зображення,
    та formset для довільної кількості додаткових фото.

    Все загорнуто в transaction.atomic() для атомарності.

    Порівняння з попередніми create views:
      - CategoryForm (2.1): лише текстові поля
      - CategoryForm + LogoForm (2.3): текст + SVG файл (FileField)
      - TagForm + LogoForm (2.5): те саме, але CBV
      - DishForm + ImageForm (2.6): FK + M2M + ImageField
      - DishForm + ImageForm + FormSet + atomic (2.6.1): все разом + транзакція

    Attributes:
        model: Dish — модель, для якої створюється об'єкт.
        form_class: DishForm — клас основної форми.
        template_name: Path to the form template.
        success_url: URL для redirect після збереження.

    """

    model = Dish
    form_class = DishForm
    template_name = "menu/dish_form.html"
    success_url = reverse_lazy("menu:dish_list")

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        """Add DishMainImageForm and DishPictureFormSet to the template context.

        Розширення get_context_data() (таска 2.6.1):
        крім image_form, додаємо picture_formset — набір форм для
        додаткових зображень. Django FormSet потребує prefix для
        генерації унікальних HTML-імен: "pictures-0-title", "pictures-1-title".

        Документація:
          https://docs.djangoproject.com/en/stable/ref/class-based-views/mixins-simple/#contextmixin
        """
        context = super().get_context_data(**kwargs)
        # --- Форма головного зображення --- #
        if "image_form" not in context:
            context["image_form"] = DishMainImageForm(prefix="main_image")
        # --- Formset додаткових зображень (таска 2.6.1) --- #
        # prefix="pictures" — HTML-імена: "pictures-0-title", "pictures-0-image" тощо
        # DishPictureFormSet(prefix=...) для GET створює extra=1 порожню форму.
        if "picture_formset" not in context:
            context["picture_formset"] = DishPictureFormSet(prefix="pictures")
        return context

    def form_valid(self, form: DishForm) -> HttpResponse:
        """Handle valid DishForm + required image + optional picture formset.

        Послідовність дій (таска 2.6.1):
        1. Створюємо image_form та picture_formset з request.POST/FILES
        2. Перевіряємо ОБОВ'ЯЗКОВІСТЬ головного зображення
        3. Валідуємо image_form та picture_formset
        4. Якщо все валідне — зберігаємо ВСЕ в transaction.atomic():
           a) Dish (form.save(commit=False) + save() + save_m2m())
           b) DishMainImage (image_form.save(commit=False) + dish= + save())
           c) DishPicture (formset.instance = dish + formset.save())

        transaction.atomic() гарантує:
          - Якщо будь-який save() кидає виключення → ROLLBACK всіх INSERT-ів
          - Або все зберігається, або нічого (ACID: Atomicity)

        Документація:
          https://docs.djangoproject.com/en/stable/topics/db/transactions/
        """
        # --- Створюємо форму зображення та formset з даних запиту --- #
        image_form = DishMainImageForm(
            self.request.POST, self.request.FILES, prefix="main_image"
        )
        picture_formset = DishPictureFormSet(
            self.request.POST, self.request.FILES, prefix="pictures"
        )

        # --- Перевіряємо ОБОВ'ЯЗКОВІСТЬ головного зображення (таска 2.6.1) --- #
        # has_image = False → користувач не завантажив файл → помилка.
        # add_error("image", ...) — додає помилку до конкретного поля форми,
        # щоб шаблон показав її біля поля, а не як загальну помилку.
        # Документація:
        #   https://docs.djangoproject.com/en/stable/ref/forms/api/#django.forms.Form.add_error
        has_image = bool(self.request.FILES.get("main_image-image"))
        if not has_image:
            image_form.add_error("image", "Головне зображення є обов'язковим.")

        # --- Валідація image_form --- #
        # is_valid() запускає всі валідатори поля image (ImageField → Pillow).
        # Якщо has_image=False, ми вже додали помилку → is_valid() поверне False.
        image_valid = image_form.is_valid()

        # --- Валідація formset --- #
        # FormSet.is_valid() перевіряє ManagementForm + кожну форму у наборі.
        # Порожні форми автоматично пропускаються (не вимагають заповнення).
        formset_valid = picture_formset.is_valid()

        if not image_valid or not formset_valid:
            # Повертаємо ВСІ форми з помилками — користувач бачить що виправити.
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    image_form=image_form,
                    picture_formset=picture_formset,
                )
            )

        # --- Транзакція: все або нічого (таска 2.6.1) --- #
        # transaction.atomic() — контекстний менеджер:
        #   - При вході: Django починає транзакцію (або SAVEPOINT у вкладених)
        #   - При нормальному виході: COMMIT — всі зміни зберігаються
        #   - При виключенні: ROLLBACK — жодна зміна не зберігається
        #
        # Без atomic(): якщо Dish.save() пройде, а DishMainImage.save() впаде —
        # в БД залишиться "сирота" Dish без зображення.
        # З atomic(): або Dish + Image + Pictures — або нічого.
        #
        # Документація:
        #   https://docs.djangoproject.com/en/stable/topics/db/transactions/#controlling-transactions-explicitly
        with transaction.atomic():
            # --- Зберігаємо Dish (commit=False + save_m2m) --- #
            # commit=False: створює Dish в пам'яті, щоб зберегти в рамках транзакції.
            # save(): зберігає в БД, Dish отримує id.
            # save_m2m(): зберігає M2M зв'язки (tags) — потребує id.
            dish = form.save(commit=False)
            dish.save()
            form.save_m2m()

            # --- Зберігаємо DishMainImage --- #
            main_image = image_form.save(commit=False)
            main_image.dish = dish
            main_image.save()

            # --- Зберігаємо DishPicture (formset) --- #
            # formset.instance = dish — зв'язує всі форми formset з цим Dish.
            # formset.save() — зберігає лише заповнені форми (порожні пропускаються).
            # Django автоматично задає picture.dish = dish для кожного DishPicture.
            picture_formset.instance = dish
            picture_formset.save()

        return redirect(self.success_url)


# ---------------------------------------------------------------------------
# DishUpdateView — редагування страви через generic UpdateView (таска 2.7)
#
# Найскладніший update у проєкті — аналогічний DishCreateView, але для UPDATE:
#   1. Django завантажує існуючу Dish по pk
#   2. DishForm заповнюється поточними даними (instance=dish)
#   3. DishMainImageForm заповнюється існуючим зображенням (instance=main_image)
#   4. DishPictureFormSet показує існуючі додаткові зображення
#   5. form.save() робить UPDATE замість INSERT
#
# Відмінності від DishCreateView:
#   - Головне зображення вже існує → НЕ вимагаємо повторного завантаження
#     (користувач може змінити зображення або залишити поточне)
#   - FormSet отримує instance=dish → показує існуючі DishPicture
#
# Документація:
#   https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-editing/#updateview
# ---------------------------------------------------------------------------
class DishUpdateView(generic.UpdateView):
    """Update an existing dish with images via generic UpdateView.

    Перевикористовує dish_form.html — шаблон підтримує create/update.

    Attributes:
        model: Dish — модель, яку редагуємо.
        form_class: DishForm — клас основної форми.
        template_name: Path to the form template (shared with DishCreateView).
        success_url: URL для redirect після збереження.

    """

    model = Dish
    form_class = DishForm
    template_name = "menu/dish_form.html"
    success_url = reverse_lazy("menu:dish_list")

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        """Add DishMainImageForm and DishPictureFormSet to the template context.

        При update:
        - image_form заповнюється існуючим DishMainImage (instance=main_image)
        - picture_formset показує існуючі DishPicture (instance=dish)
        """
        context = super().get_context_data(**kwargs)
        dish = self.object

        if "image_form" not in context:
            # --- Головне зображення: показуємо існуюче --- #
            existing_image = getattr(dish, "main_image", None)
            context["image_form"] = DishMainImageForm(
                prefix="main_image", instance=existing_image
            )

        if "picture_formset" not in context:
            # --- Додаткові зображення: показуємо існуючі --- #
            # instance=dish → formset завантажить всі DishPicture для цього dish
            context["picture_formset"] = DishPictureFormSet(
                prefix="pictures", instance=dish
            )

        return context

    def form_valid(self, form: DishForm) -> HttpResponse:
        """Handle valid DishForm + optional image update + formset.

        Відмінності від DishCreateView.form_valid():
        - Якщо користувач не завантажує новий файл → зображення не змінюється
        - Якщо завантажує → оновлюємо існуючий DishMainImage (instance=...)
        - FormSet оновлює/додає DishPicture
        """
        dish = self.object
        existing_image = getattr(dish, "main_image", None)

        # --- Створюємо image_form та formset з даних запиту --- #
        image_form = DishMainImageForm(
            self.request.POST,
            self.request.FILES,
            prefix="main_image",
            instance=existing_image,
        )
        picture_formset = DishPictureFormSet(
            self.request.POST,
            self.request.FILES,
            prefix="pictures",
            instance=dish,
        )

        # --- При update: зображення вже існує, нове — опціональне --- #
        # На відміну від create, де зображення обов'язкове,
        # при update ми дозволяємо залишити поточне зображення.
        has_new_image = bool(self.request.FILES.get("main_image-image"))
        if not existing_image and not has_new_image:
            image_form.add_error("image", "Головне зображення є обов'язковим.")

        image_valid = image_form.is_valid() if has_new_image else True
        formset_valid = picture_formset.is_valid()

        if not image_valid or not formset_valid:
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    image_form=image_form,
                    picture_formset=picture_formset,
                )
            )

        with transaction.atomic():
            dish = form.save()

            if has_new_image:
                main_image = image_form.save(commit=False)
                main_image.dish = dish
                main_image.save()

            picture_formset.instance = dish
            picture_formset.save()

        return redirect(self.success_url)


# ---------------------------------------------------------------------------
# DishDeleteView — видалення страви через generic DeleteView (таска 2.7)
#
# При видаленні страви каскадно видаляються:
#   - DishMainImage (OneToOne, CASCADE) — головне зображення
#   - DishPicture (ForeignKey, CASCADE) — всі додаткові зображення
#   - Dish.tags M2M записи — зв'язки з тегами у проміжній таблиці
#
# На відміну від CategoryDeleteView, тут не потрібен список дочірніх об'єктів,
# бо страва — це кінцевий об'єкт (не має вкладених страв).
# Показуємо інформацію про зображення, що будуть видалені.
#
# Документація:
#   https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-editing/#deleteview
# ---------------------------------------------------------------------------
class DishDeleteView(generic.DeleteView):
    """Delete a dish with confirmation showing related images.

    GET shows confirmation page with image count.
    POST deletes the dish and all related images (CASCADE).

    Attributes:
        model: Dish — модель, яку видаляємо.
        template_name: Path to the confirmation template.
        success_url: URL для redirect після видалення.
        context_object_name: Name of the variable in the template context.

    """

    model = Dish
    template_name = "menu/dish_confirm_delete.html"
    success_url = reverse_lazy("menu:dish_list")
    context_object_name = "dish"

    def get_queryset(self) -> models.QuerySet[Dish]:
        """Optimize query: prefetch images for the confirmation page.

        select_related("main_image") — JOIN для OneToOne.
        prefetch_related("additional_images") — окремий запит для FK reverse.
        """
        return Dish.objects.select_related("main_image").prefetch_related(
            "additional_images"
        )


# ---------------------------------------------------------------------------
# dish_search — пошук страв через Q-objects (таска 3.1)
#
# Q-objects дозволяють будувати складні SQL WHERE з OR/AND:
#   Q(title__icontains=q) | Q(description__icontains=q)
#   → WHERE title ILIKE '%q%' OR description ILIKE '%q%'
#
# icontains — регістронезалежний пошук підрядка.
# Для SQLite (dev) використовує LIKE, для PostgreSQL (prod) — ILIKE.
#
# Документація Q-objects:
#   https://docs.djangoproject.com/en/stable/topics/db/queries/#complex-lookups-with-q-objects
# Документація icontains:
#   https://docs.djangoproject.com/en/stable/ref/models/querysets/#icontains
# ---------------------------------------------------------------------------
def dish_search(request: HttpRequest) -> HttpResponse:
    """Search dishes by title and description.

    GET parameters:
        q: Search query string. Empty query returns no results.

    Context:
        query: The search query entered by the user.
        dishes: QuerySet of matching Dish objects (empty if no query).

    """
    query = request.GET.get("q", "").strip()
    dishes = Dish.objects.none()

    if query:
        # --- Q-objects: OR-запит по назві та описі страви --- #
        # Шукаємо збіги в:
        #   1. title страви — назва ("Борщ", "Цезар")
        #   2. description страви — опис ("традиційний суп", "з куркою")
        #
        # | (pipe) — логічне OR між Q-objects.
        # Документація:
        #   https://docs.djangoproject.com/en/stable/topics/db/queries/#complex-lookups-with-q-objects
        dishes = (
            Dish.objects.filter(
                Q(title__icontains=query) | Q(description__icontains=query)
            )
            .select_related("category__logo")
            .prefetch_related("tags__logo")
        )

    return render(
        request,
        "menu/search_results.html",
        {"query": query, "dishes": dishes},
    )
