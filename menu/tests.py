# ---------------------------------------------------------------------------
# Тести для застосунку menu
#
# Використовуємо Django TestCase — базовий клас для тестів з підтримкою
# тестової бази даних, клієнта (self.client) та транзакцій.
#
# Кожен тест-метод починається з test_ — pytest автоматично їх знаходить.
# self.client — тестовий HTTP-клієнт Django для імітації запитів.
#
# Запуск: uv run pytest
# Документація:
#   https://docs.djangoproject.com/en/stable/topics/testing/
#   https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.TestCase
# ---------------------------------------------------------------------------

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from menu.models import (
    Category,
    CategoryLogo,
    Dish,
    DishMainImage,
    DishPicture,
    Tag,
    TagLogo,
)
from menu.templatetags.menu_extras import highlight
from menu.validators import validate_svg_content


class IndexViewTest(TestCase):
    """Test the index (home) view at /menu/."""

    def test_index_returns_200(self) -> None:
        """GET /menu/ повинен повертати HTTP 200 OK."""
        response = self.client.get("/menu/")
        self.assertEqual(response.status_code, 200)

    def test_index_uses_correct_template(self) -> None:
        """View index повинна рендерити шаблон menu/index.html.

        assertTemplateUsed — метод Django TestCase, що перевіряє
        який саме шаблон був використаний для рендерингу відповіді.
        Документація:
          https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.SimpleTestCase.assertTemplateUsed
        """
        response = self.client.get("/menu/")
        self.assertTemplateUsed(response, "menu/index.html")

    def test_index_contains_slides(self) -> None:
        """Контекст повинен містити непорожній список slides.

        response.context — словник контексту, переданий у шаблон.
        Доступний тільки у тестових відповідях Django TestCase.
        Документація:
          https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.Response.context
        """
        response = self.client.get("/menu/")
        slides = response.context["slides"]
        self.assertIsInstance(slides, list)
        self.assertGreater(len(slides), 0)

    def test_index_contains_carousel_markup(self) -> None:
        """HTML відповіді повинен містити розмітку Bootstrap Carousel.

        assertContains — перевіряє, що рядок присутній у тілі відповіді.
        Документація:
          https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.SimpleTestCase.assertContains
        """
        response = self.client.get("/menu/")
        self.assertContains(response, 'id="mainCarousel"')
        self.assertContains(response, "carousel-item")


class CategoryListViewTest(TestCase):
    """Test the category list view at /menu/categories/.

    setUpTestData — метод класу, що створює тестові дані один раз
    для всього TestCase (швидше ніж setUp, який створює для кожного тесту).
    Документація:
      https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.TestCase.setUpTestData
    """

    cat: Category

    @classmethod
    def setUpTestData(cls) -> None:
        """Create test category with one dish."""
        cls.cat = Category.objects.create(title="Салати", description="Свіжі салати")
        Dish.objects.create(
            title="Цезар",
            description="Класичний салат",
            price=12.50,
            weight=350,
            calorie=420,
            category=cls.cat,
        )

    def test_category_list_returns_200(self) -> None:
        """GET /menu/categories/ повинен повертати HTTP 200 OK."""
        response = self.client.get("/menu/categories/")
        self.assertEqual(response.status_code, 200)

    def test_category_list_uses_correct_template(self) -> None:
        """View повинна рендерити шаблон menu/category_list.html."""
        response = self.client.get("/menu/categories/")
        self.assertTemplateUsed(response, "menu/category_list.html")

    def test_category_list_shows_categories(self) -> None:
        """Відповідь повинна містити назву категорії.

        assertContains перевіряє і status_code == 200, і наявність тексту.
        """
        response = self.client.get("/menu/categories/")
        self.assertContains(response, "Салати")

    def test_category_list_shows_dishes(self) -> None:
        """Відповідь повинна містити назву страви з цієї категорії."""
        response = self.client.get("/menu/categories/")
        self.assertContains(response, "Цезар")

    def test_category_list_has_accordion(self) -> None:
        """HTML повинен містити розмітку Bootstrap Accordion."""
        response = self.client.get("/menu/categories/")
        self.assertContains(response, 'id="accMenu"')
        self.assertContains(response, "accordion-item")


class CategoryOrderingTest(TestCase):
    """Test that categories are ordered by number_in_line.

    Meta.ordering — визначає порядок за замовчуванням для всіх QuerySet.
    Перевіряємо, що Category.objects.all() повертає категорії
    у порядку зростання number_in_line.

    Документація:
      https://docs.djangoproject.com/en/stable/ref/models/options/#ordering
    """

    @classmethod
    def setUpTestData(cls) -> None:
        """Create categories in non-sequential order."""
        Category.objects.create(title="Десерти", description="...", number_in_line=3)
        Category.objects.create(title="Салати", description="...", number_in_line=1)
        Category.objects.create(title="М'ясо", description="...", number_in_line=2)

    def test_categories_ordered_by_number(self) -> None:
        """QuerySet повинен повертати категорії у порядку number_in_line."""
        cats = list(Category.objects.values_list("title", flat=True))
        self.assertEqual(cats, ["Салати", "М'ясо", "Десерти"])


class CategoryListQueryTest(TestCase):
    """Test that category_list view is optimized (no N+1 queries).

    assertNumQueries — перевіряє точну кількість SQL-запитів у блоці.
    Документація:
      https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.TransactionTestCase.assertNumQueries
    """

    @classmethod
    def setUpTestData(cls) -> None:
        """Create 5 categories with 3 dishes each, some with tags."""
        tag = Tag.objects.create(title="Веган", description="Без тваринних продуктів")
        for i in range(5):
            cat = Category.objects.create(title=f"Cat {i}", description="...")
            for j in range(3):
                dish = Dish.objects.create(
                    title=f"Dish {i}-{j}",
                    description="...",
                    price=10,
                    weight=200,
                    calorie=300,
                    category=cat,
                )
                dish.tags.add(tag)

    def test_category_list_query_count(self) -> None:
        """Сторінка /menu/categories/ повинна виконувати ≤ 4 SQL-запити.

        З prefetch_related + select_related:
          1. categories + category_logos (select_related JOIN)
          2. dishes (prefetch_related)
          3. tags + tag_logos (prefetch з select_related JOIN)
          4. allergens (prefetch_related)
        Разом: 4 SQL-запити.
        """
        with self.assertNumQueries(4):
            self.client.get("/menu/categories/")


# ---------------------------------------------------------------------------
# Тести для TagListView (таска 1.8)
#
# TagListView — перший CBV (Class-Based View) у проєкті.
# Перевіряємо: HTTP 200, правильний шаблон, відображення тегів і страв,
# групування страв по категоріях ({% regroup %}), оптимізацію запитів.
# ---------------------------------------------------------------------------
class TagListViewTest(TestCase):
    """Test the tag list view at /menu/tags/.

    Перевіряємо що TagListView (generic ListView) коректно
    відображає теги зі стравами, згрупованими по категоріях.
    """

    tag: Tag
    cat: Category

    @classmethod
    def setUpTestData(cls) -> None:
        """Create a tag with one dish in a category."""
        cls.tag = Tag.objects.create(
            title="Веган", description="Без тваринних продуктів"
        )
        cls.cat = Category.objects.create(
            title="Салати", description="...", number_in_line=1
        )
        dish = Dish.objects.create(
            title="Овочевий мікс",
            description="Свіжі сезонні овочі",
            price=9,
            weight=300,
            calorie=150,
            category=cls.cat,
        )
        # dish.tags.add() — додає зв'язок ManyToMany між стравою і тегом.
        # Документація:
        #   https://docs.djangoproject.com/en/stable/ref/models/relations/#django.db.models.fields.related.RelatedManager.add
        dish.tags.add(cls.tag)

    def test_tag_list_returns_200(self) -> None:
        """GET /menu/tags/ повинен повертати HTTP 200 OK."""
        response = self.client.get("/menu/tags/")
        self.assertEqual(response.status_code, 200)

    def test_tag_list_uses_correct_template(self) -> None:
        """View повинна рендерити шаблон menu/tag_list.html."""
        response = self.client.get("/menu/tags/")
        self.assertTemplateUsed(response, "menu/tag_list.html")

    def test_tag_list_shows_tag(self) -> None:
        """Відповідь повинна містити назву тега."""
        response = self.client.get("/menu/tags/")
        self.assertContains(response, "Веган")

    def test_tag_list_shows_dishes(self) -> None:
        """Відповідь повинна містити назву страви, пов'язаної з тегом."""
        response = self.client.get("/menu/tags/")
        self.assertContains(response, "Овочевий мікс")

    def test_tag_list_shows_category_grouping(self) -> None:
        """Страви повинні бути згруповані по категоріях ({% regroup %}).

        Перевіряємо що назва категорії відображається як підзаголовок
        всередині accordion-body тега.
        """
        response = self.client.get("/menu/tags/")
        self.assertContains(response, "Салати")

    def test_tag_list_has_accordion(self) -> None:
        """HTML повинен містити розмітку Bootstrap Accordion."""
        response = self.client.get("/menu/tags/")
        self.assertContains(response, 'id="accTags"')
        self.assertContains(response, "accordion-item")


class TagListQueryTest(TestCase):
    """Test that tag_list view is optimized (no N+1 queries).

    Аналогічно до CategoryListQueryTest — перевіряємо
    кількість SQL-запитів при великій кількості даних.
    """

    @classmethod
    def setUpTestData(cls) -> None:
        """Create 5 tags with dishes across 3 categories."""
        cats = [
            Category.objects.create(
                title=f"Cat {i}", description="...", number_in_line=i
            )
            for i in range(3)
        ]
        for i in range(5):
            tag = Tag.objects.create(title=f"Tag {i}", description="...")
            for cat in cats:
                dish = Dish.objects.create(
                    title=f"Dish {tag.title}-{cat.title}",
                    description="...",
                    price=10,
                    weight=200,
                    calorie=300,
                    category=cat,
                )
                dish.tags.add(tag)

    def test_tag_list_query_count(self) -> None:
        """Сторінка /menu/tags/ повинна виконувати ≤ 2 SQL-запити.

        Без оптимізації: 1 (tags) + N (dishes per tag) + N*M (categories).
        З оптимізацією: 2 запити:
          1. Tags + JOIN TagLogo (select_related("logo"))
          2. Dishes + JOIN Category (select_related("category") у Prefetch)
        """
        with self.assertNumQueries(2):
            self.client.get("/menu/tags/")


# ---------------------------------------------------------------------------
# Тести для dish_detail (таска 1.9)
#
# Перевіряємо: HTTP 200, правильний шаблон, відображення інформації,
# 404 для неіснуючої страви, оптимізацію запитів.
# ---------------------------------------------------------------------------
class DishDetailViewTest(TestCase):
    """Test the dish detail view at /menu/dishes/<pk>/.

    Перевіряємо що dish_detail коректно відображає повну
    інформацію про страву: назва, опис, ціна, категорія, теги.
    """

    cat: Category
    dish: Dish

    @classmethod
    def setUpTestData(cls) -> None:
        """Create a dish with category and tag."""
        cls.cat = Category.objects.create(
            title="Салати", description="...", number_in_line=1
        )
        cls.dish = Dish.objects.create(
            title="Цезар",
            description="Класичний салат Цезар з куркою",
            price=12.50,
            weight=350,
            calorie=420,
            category=cls.cat,
        )
        tag = Tag.objects.create(title="Шеф рекомендує", description="...")
        cls.dish.tags.add(tag)

    def test_dish_detail_returns_200(self) -> None:
        """GET /menu/dishes/<pk>/ повинен повертати HTTP 200 OK."""
        response = self.client.get(f"/menu/dishes/{self.dish.pk}/")
        self.assertEqual(response.status_code, 200)

    def test_dish_detail_uses_correct_template(self) -> None:
        """View повинна рендерити шаблон menu/dish_detail.html."""
        response = self.client.get(f"/menu/dishes/{self.dish.pk}/")
        self.assertTemplateUsed(response, "menu/dish_detail.html")

    def test_dish_detail_shows_info(self) -> None:
        """Відповідь повинна містити назву, опис та ціну страви."""
        response = self.client.get(f"/menu/dishes/{self.dish.pk}/")
        self.assertContains(response, "Цезар")
        self.assertContains(response, "Класичний салат Цезар з куркою")
        self.assertContains(response, "12,50")

    def test_dish_detail_shows_category(self) -> None:
        """Відповідь повинна містити назву категорії страви."""
        response = self.client.get(f"/menu/dishes/{self.dish.pk}/")
        self.assertContains(response, "Салати")

    def test_dish_detail_shows_tags(self) -> None:
        """Відповідь повинна містити назви тегів страви."""
        response = self.client.get(f"/menu/dishes/{self.dish.pk}/")
        self.assertContains(response, "Шеф рекомендує")

    def test_dish_detail_404_for_nonexistent(self) -> None:
        """Неіснуюча страва повинна повертати HTTP 404.

        get_object_or_404 автоматично піднімає Http404
        якщо об'єкт не знайдено в базі.
        Документація:
          https://docs.djangoproject.com/en/stable/topics/http/shortcuts/#get-object-or-404
        """
        response = self.client.get("/menu/dishes/99999/")
        self.assertEqual(response.status_code, 404)

    def test_dish_detail_has_back_button(self) -> None:
        """Сторінка повинна містити кнопку "Назад"."""
        response = self.client.get(f"/menu/dishes/{self.dish.pk}/")
        self.assertContains(response, "history.back()")


# ---------------------------------------------------------------------------
# Тести для category_create (таска 2.1)
#
# Перевіряємо повну механіку Django-форм:
# - GET: порожня форма рендериться
# - POST (valid): створює Category → redirect на category_list
# - POST (invalid): повертає форму з помилками, дані не зберігаються
# ---------------------------------------------------------------------------
class CategoryCreateTest(TestCase):
    """Test the category creation form at /menu/categories/create/.

    Демонструє тестування FBV з формою:
    - self.client.get() — імітує GET-запит (показ форми)
    - self.client.post() — імітує POST-запит (відправка форми)
    - assertRedirects — перевіряє HTTP 302 та URL редиректу

    Документація assertRedirects:
      https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.SimpleTestCase.assertRedirects
    """

    def test_create_form_get(self) -> None:
        """GET /menu/categories/create/ повинен показати порожню форму."""
        response = self.client.get("/menu/categories/create/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<form")
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_create_form_has_enctype(self) -> None:
        """Форма повинна мати enctype="multipart/form-data" для файлів.

        Без цього атрибуту браузер НЕ відправляє завантажені файли,
        і request.FILES буде порожнім. Це найчастіша помилка при file upload.
        Документація:
          https://docs.djangoproject.com/en/stable/topics/http/file-uploads/
        """
        response = self.client.get("/menu/categories/create/")
        self.assertContains(response, 'enctype="multipart/form-data"')

    def test_create_form_has_logo_section(self) -> None:
        """GET повинен показати секцію для завантаження логотипу.

        View передає logo_form у контекст, шаблон рендерить її
        як окрему секцію з полями logo-title та logo-image (prefix="logo").
        """
        response = self.client.get("/menu/categories/create/")
        self.assertContains(response, "Логотип категорії")
        # prefix="logo" — поля мають HTML-імена logo-title, logo-image
        self.assertContains(response, 'name="logo-title"')
        self.assertContains(response, 'name="logo-image"')

    def test_create_category_post_valid(self) -> None:
        """POST з валідними даними → створює Category → redirect.

        assertRedirects перевіряє:
          1. Статус-код 302 (redirect)
          2. URL редиректу == /menu/categories/
        """
        data = {
            "title": "Піца",
            "description": "Італійська піца",
            "number_in_line": 5,
        }
        response = self.client.post("/menu/categories/create/", data)
        self.assertRedirects(response, "/menu/categories/")
        self.assertTrue(Category.objects.filter(title="Піца").exists())

    def test_create_category_without_logo(self) -> None:
        """POST без логотипу — категорія створюється, логотип не створюється.

        Логотип є опціональним: користувач може створити категорію
        без завантаження SVG-файлу.
        """
        data = {
            "title": "Напої",
            "description": "Холодні та гарячі",
            "number_in_line": 8,
        }
        response = self.client.post("/menu/categories/create/", data)
        self.assertRedirects(response, "/menu/categories/")
        self.assertTrue(Category.objects.filter(title="Напої").exists())
        self.assertFalse(CategoryLogo.objects.exists())

    def test_create_category_post_invalid(self) -> None:
        """POST з невалідними даними → форма з помилками, без редиректу.

        При невалідному POST:
          - HTTP 200 (не 302) — форма рендериться повторно
          - Об'єкт НЕ створюється в БД
          - Форма містить помилки (form.errors)
        """
        response = self.client.post("/menu/categories/create/", {"title": ""})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Category.objects.exists())


# ---------------------------------------------------------------------------
# Тести для створення категорії з логотипом (таска 2.3)
#
# Перевіряємо обробку ДВОХ форм в одному view:
# - CategoryForm (текстові дані) + CategoryLogoForm (файл SVG)
# - request.FILES та SimpleUploadedFile для імітації завантаження
# - prefix="logo" для розділення однойменних полів
# - save(commit=False) для зв'язування логотипу з категорією
#
# SimpleUploadedFile — тестовий клас Django для імітації завантаження файлу.
# Документація:
#   https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.SimpleUploadedFile
# ---------------------------------------------------------------------------
class CategoryCreateWithLogoTest(TestCase):
    """Test category creation with logo upload at /menu/categories/create/.

    Перевіряємо що view коректно обробляє дві форми одночасно:
    CategoryForm (дані категорії) + CategoryLogoForm (SVG-логотип).
    """

    def _make_svg(self, name: str = "logo.svg") -> SimpleUploadedFile:
        """Create a minimal valid SVG file for testing.

        SimpleUploadedFile(name, content, content_type) — створює
        об'єкт, що імітує завантажений файл без реального файлу на диску.
        """
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
        return SimpleUploadedFile(name, svg_content, content_type="image/svg+xml")

    def test_create_category_with_logo(self) -> None:
        """POST з категорією + SVG-логотипом → створює обидва об'єкти.

        Дані форми з prefix="logo" мають HTML-імена "logo-title", "logo-image".
        request.FILES["logo-image"] — завантажений SVG-файл.

        Перевіряємо:
          1. Category створена
          2. CategoryLogo створена
          3. CategoryLogo.category вказує на створену Category (OneToOne)
        """
        data = {
            "title": "Салати",
            "description": "Свіжі салати",
            "number_in_line": 1,
            # prefix="logo" → поля форми мають HTML-імена "logo-title", "logo-image"
            "logo-title": "Іконка салатів",
            "logo-image": self._make_svg(),
        }
        response = self.client.post("/menu/categories/create/", data)
        self.assertRedirects(response, "/menu/categories/")

        # Перевіряємо що Category створена
        category = Category.objects.get(title="Салати")

        # Перевіряємо що CategoryLogo створена і зв'язана з Category
        self.assertTrue(CategoryLogo.objects.filter(category=category).exists())
        logo = CategoryLogo.objects.get(category=category)
        self.assertEqual(logo.title, "Іконка салатів")

    def test_logo_linked_to_category(self) -> None:
        """CategoryLogo.category повинен вказувати на створену Category.

        Перевіряємо OneToOne зв'язок: category.logo працює
        (зворотній доступ через related_name="logo").
        """
        data = {
            "title": "Десерти",
            "description": "Солодкі страви",
            "number_in_line": 7,
            "logo-title": "Десертна іконка",
            "logo-image": self._make_svg(),
        }
        self.client.post("/menu/categories/create/", data)

        category = Category.objects.get(title="Десерти")
        # category.logo — зворотній OneToOne доступ через related_name.
        self.assertEqual(category.logo.title, "Десертна іконка")

    def test_invalid_category_with_logo_not_saved(self) -> None:
        """Невалідна категорія → ні Category, ні Logo не створюються.

        Якщо основна форма невалідна (title=""), логотип також
        НЕ зберігається — атомарність операції.
        """
        data = {
            "title": "",  # невалідне — title обов'язковий
            "description": "Опис",
            "number_in_line": 1,
            "logo-title": "Логотип",
            "logo-image": self._make_svg(),
        }
        response = self.client.post("/menu/categories/create/", data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Category.objects.exists())
        self.assertFalse(CategoryLogo.objects.exists())


# ---------------------------------------------------------------------------
# Тести для TagCreateView (таска 2.2)
#
# Аналогічно до CategoryCreateTest, але тут view — generic CreateView (CBV),
# а не FBV. Перевіряємо ту саму логіку:
# - GET: порожня форма рендериться
# - POST (valid): створює Tag → redirect на tag_list
# - POST (invalid): повертає форму з помилками, дані не зберігаються
#
# Порівняння підходів:
#   CategoryCreateTest → тестує FBV (ручна обробка GET/POST)
#   TagCreateTest → тестує CBV (Django обробляє все автоматично)
#   Тести ОДНАКОВІ — поведінка ідентична, різниця лише у реалізації view.
#
# Документація generic CreateView:
#   https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-editing/#createview
# ---------------------------------------------------------------------------
class TagCreateTest(TestCase):
    """Test the tag creation form at /menu/tags/create/.

    Перевіряємо що generic CreateView коректно обробляє
    створення нового тега: форма, валідація, збереження, редирект.
    """

    def test_create_form_get(self) -> None:
        """GET /menu/tags/create/ повинен показати порожню форму.

        CreateView автоматично створює порожній TagForm()
        і рендерить шаблон tag_form.html.
        """
        response = self.client.get("/menu/tags/create/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<form")
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_create_form_uses_correct_template(self) -> None:
        """View повинна рендерити шаблон menu/tag_form.html."""
        response = self.client.get("/menu/tags/create/")
        self.assertTemplateUsed(response, "menu/tag_form.html")

    def test_create_tag_post_valid(self) -> None:
        """POST з валідними даними → створює Tag → redirect на tag_list.

        CreateView автоматично:
          1. Створює TagForm(request.POST)
          2. Викликає form.is_valid()
          3. Викликає form.save()
          4. Робить redirect на success_url (menu:tag_list)

        assertRedirects перевіряє HTTP 302 та URL редиректу.
        Документація:
          https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.SimpleTestCase.assertRedirects
        """
        data = {"title": "Дитяче", "description": "Підходить для дітей"}
        response = self.client.post("/menu/tags/create/", data)
        self.assertRedirects(response, "/menu/tags/")
        self.assertTrue(Tag.objects.filter(title="Дитяче").exists())

    def test_create_tag_post_invalid(self) -> None:
        """POST з невалідними даними → форма з помилками, без редиректу.

        При невалідному POST CreateView автоматично:
          - Повертає HTTP 200 (не 302)
          - Рендерить шаблон з формою, що містить помилки
          - НЕ зберігає об'єкт у БД
        """
        response = self.client.post("/menu/tags/create/", {"title": ""})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Tag.objects.exists())


# ---------------------------------------------------------------------------
# Тести для validate_svg_content (таска 2.4)
#
# Тестуємо кастомний валідатор — функцію, що перевіряє ВМІСТ файлу,
# а не лише розширення. Валідатор приймає UploadedFile і або
# нічого не повертає (валідний файл), або піднімає ValidationError.
#
# SimpleUploadedFile — тестовий інструмент Django для імітації
# завантаження файлу без реального файлу на диску.
#
# Документація:
#   https://docs.djangoproject.com/en/stable/ref/validators/
#   https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.SimpleUploadedFile
# ---------------------------------------------------------------------------
class SVGValidatorTest(TestCase):
    """Test the validate_svg_content custom validator.

    Перевіряємо два сценарії:
    1. Валідний SVG → функція нічого не повертає (без помилок)
    2. Невалідний файл → функція піднімає ValidationError

    Це unit-тести валідатора — тестуємо функцію напряму,
    без HTTP-запитів (швидше та надійніше ніж через view).
    """

    def test_valid_svg_passes(self) -> None:
        """Файл з коректним SVG-вмістом проходить валідацію.

        Мінімальний валідний SVG: <svg> з довільним вмістом.
        Валідатор НЕ піднімає виключення → тест проходить.
        """
        svg = SimpleUploadedFile(
            "ok.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>',
            content_type="image/svg+xml",
        )
        # Якщо валідатор не кидає виключення — файл валідний.
        validate_svg_content(svg)

    def test_valid_svg_with_xml_header_passes(self) -> None:
        """SVG з XML-декларацією на початку проходить валідацію.

        Деякі SVG-редактори додають <?xml version="1.0"?> перед <svg>.
        Валідатор повинен розпізнавати обидва варіанти.
        """
        svg = SimpleUploadedFile(
            "ok.svg",
            b'<?xml version="1.0" encoding="UTF-8"?><svg><circle/></svg>',
            content_type="image/svg+xml",
        )
        validate_svg_content(svg)

    def test_png_content_in_svg_extension_fails(self) -> None:
        """Файл з розширенням .svg, але вмістом PNG — НЕ проходить.

        Це головний кейс: FileExtensionValidator пропустить файл
        (розширення .svg), але validate_svg_content заблокує
        (вміст починається з PNG-заголовка 0x89 PNG, а не <svg>).

        assertRaises — перевіряє що блок коду піднімає виключення.
        Документація:
          https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertRaises
        """
        fake_svg = SimpleUploadedFile(
            "fake.svg",
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
            content_type="image/svg+xml",
        )
        with self.assertRaises(ValidationError) as ctx:
            validate_svg_content(fake_svg)
        # Перевіряємо code помилки — дозволяє програмно розрізняти типи помилок.
        self.assertEqual(ctx.exception.code, "invalid_svg")

    def test_jpeg_content_fails(self) -> None:
        """JPEG-файл, перейменований у .svg — НЕ проходить.

        JPEG починається з байтів 0xFF 0xD8 0xFF — це не SVG.
        """
        fake_svg = SimpleUploadedFile(
            "photo.svg",
            b"\xff\xd8\xff\xe0\x00\x10JFIF",
            content_type="image/svg+xml",
        )
        with self.assertRaises(ValidationError):
            validate_svg_content(fake_svg)

    def test_empty_file_fails(self) -> None:
        """Порожній файл — НЕ проходить валідацію.

        Порожній файл не містить ні <svg>, ні <?xml> заголовка.
        """
        empty = SimpleUploadedFile(
            "empty.svg",
            b"",
            content_type="image/svg+xml",
        )
        with self.assertRaises(ValidationError):
            validate_svg_content(empty)

    def test_plain_text_fails(self) -> None:
        """Звичайний текстовий файл з розширенням .svg — НЕ проходить."""
        text_file = SimpleUploadedFile(
            "text.svg",
            b"Hello, this is just a text file!",
            content_type="image/svg+xml",
        )
        with self.assertRaises(ValidationError):
            validate_svg_content(text_file)

    def test_file_seek_reset_after_validation(self) -> None:
        """Після валідації курсор файлу повинен бути на початку.

        Це КРИТИЧНО: якщо seek(0) не викликаний після read(),
        Django не зможе зберегти файл на диск (курсор в кінці).
        """
        svg = SimpleUploadedFile(
            "ok.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>',
            content_type="image/svg+xml",
        )
        validate_svg_content(svg)
        # Перевіряємо що курсор на позиції 0 (початок файлу).
        # tell() повертає поточну позицію курсора.
        self.assertEqual(svg.tell(), 0)


# ---------------------------------------------------------------------------
# Інтеграційний тест: валідатор через форму (таска 2.4)
#
# Перевіряємо що валідатор працює не тільки напряму (unit test вище),
# а й через Django form validation pipeline:
#   POST → form = CategoryLogoForm(request.POST, request.FILES)
#   → form.is_valid() → викликає валідатори → повертає помилку
# ---------------------------------------------------------------------------
class CategoryLogoValidationIntegrationTest(TestCase):
    """Test SVG validator integration via category creation form.

    Перевіряємо що невалідний файл блокується на рівні форми,
    а валідний — проходить і створює об'єкт.
    """

    def test_create_category_with_invalid_logo_shows_error(self) -> None:
        """POST з невалідним SVG → форма повертається з помилкою.

        Файл має розширення .svg, але вміст — PNG.
        FileExtensionValidator пропустить, validate_svg_content заблокує.
        Категорія та логотип НЕ створюються.
        """
        fake_svg = SimpleUploadedFile(
            "fake.svg",
            b"\x89PNG\r\n\x1a\n\x00\x00",
            content_type="image/svg+xml",
        )
        data = {
            "title": "Салати",
            "description": "Свіжі салати",
            "number_in_line": 1,
            "logo-title": "Іконка",
            "logo-image": fake_svg,
        }
        response = self.client.post("/menu/categories/create/", data)
        # Форма повертається з помилками (HTTP 200, не 302)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Category.objects.exists())
        self.assertFalse(CategoryLogo.objects.exists())

    def test_create_category_with_valid_logo_succeeds(self) -> None:
        """POST з валідним SVG → Category + CategoryLogo створюються."""
        valid_svg = SimpleUploadedFile(
            "logo.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="5"/></svg>',
            content_type="image/svg+xml",
        )
        data = {
            "title": "Десерти",
            "description": "Солодощі",
            "number_in_line": 7,
            "logo-title": "Десертна іконка",
            "logo-image": valid_svg,
        }
        response = self.client.post("/menu/categories/create/", data)
        self.assertRedirects(response, "/menu/categories/")
        self.assertTrue(Category.objects.filter(title="Десерти").exists())
        self.assertTrue(CategoryLogo.objects.exists())


# ---------------------------------------------------------------------------
# Тести для TagCreateView з логотипом (таска 2.5)
#
# Закріплення: той самий патерн "дві форми в одному view",
# але реалізований у CBV (get_context_data + form_valid)
# замість FBV (if/else + render).
#
# Перевіряємо:
# - GET показує обидві форми (основну + логотип)
# - POST з валідним SVG створює Tag + TagLogo
# - POST без логотипу створює тільки Tag
# - POST з невалідним SVG показує помилку
# - OneToOne зв'язок Tag ↔ TagLogo
# ---------------------------------------------------------------------------
class TagCreateWithLogoTest(TestCase):
    """Test tag creation with logo upload at /menu/tags/create/.

    Закріплення патерну з CategoryCreateWithLogoTest:
    CBV (TagCreateView) обробляє TagForm + TagLogoForm через
    перевизначення get_context_data() та form_valid().
    """

    def _make_svg(self, name: str = "logo.svg") -> SimpleUploadedFile:
        """Create a minimal valid SVG file for testing."""
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
        return SimpleUploadedFile(name, svg_content, content_type="image/svg+xml")

    def test_form_has_enctype(self) -> None:
        """Форма повинна мати enctype="multipart/form-data" для файлів."""
        response = self.client.get("/menu/tags/create/")
        self.assertContains(response, 'enctype="multipart/form-data"')

    def test_form_has_logo_section(self) -> None:
        """GET повинен показати секцію для завантаження логотипу.

        CBV передає logo_form через get_context_data().
        prefix="logo" → поля мають HTML-імена logo-title, logo-image.
        """
        response = self.client.get("/menu/tags/create/")
        self.assertContains(response, "Логотип тега")
        self.assertContains(response, 'name="logo-title"')
        self.assertContains(response, 'name="logo-image"')

    def test_create_tag_with_logo(self) -> None:
        """POST з тегом + SVG-логотипом → створює обидва об'єкти.

        form_valid() у CBV:
          1. Зберігає Tag (form.save())
          2. Створює TagLogo з tag=щойно_створений_тег (logo_form.save(commit=False))
        """
        data = {
            "title": "Веган",
            "description": "Без тваринних продуктів",
            "logo-title": "Іконка вегана",
            "logo-image": self._make_svg(),
        }
        response = self.client.post("/menu/tags/create/", data)
        self.assertRedirects(response, "/menu/tags/")

        tag = Tag.objects.get(title="Веган")
        self.assertTrue(TagLogo.objects.filter(tag=tag).exists())
        self.assertEqual(tag.logo.title, "Іконка вегана")

    def test_create_tag_without_logo(self) -> None:
        """POST без логотипу — тег створюється, логотип не створюється."""
        data = {"title": "Гостре", "description": "Гострі страви"}
        response = self.client.post("/menu/tags/create/", data)
        self.assertRedirects(response, "/menu/tags/")
        self.assertTrue(Tag.objects.filter(title="Гостре").exists())
        self.assertFalse(TagLogo.objects.exists())

    def test_create_tag_with_invalid_logo_shows_error(self) -> None:
        """POST з невалідним SVG → форма повертається з помилкою.

        validate_svg_content блокує PNG-файл з розширенням .svg.
        Ні Tag, ні TagLogo НЕ створюються.
        """
        fake_svg = SimpleUploadedFile(
            "fake.svg",
            b"\x89PNG\r\n\x1a\n\x00\x00",
            content_type="image/svg+xml",
        )
        data = {
            "title": "Веган",
            "description": "Без тваринних продуктів",
            "logo-title": "Іконка",
            "logo-image": fake_svg,
        }
        response = self.client.post("/menu/tags/create/", data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Tag.objects.exists())
        self.assertFalse(TagLogo.objects.exists())

    def test_invalid_tag_with_logo_not_saved(self) -> None:
        """Невалідний тег → ні Tag, ні TagLogo не створюються.

        Атомарність: якщо основна форма невалідна, логотип теж не зберігається.
        """
        data = {
            "title": "",  # невалідне
            "description": "Опис",
            "logo-title": "Логотип",
            "logo-image": self._make_svg(),
        }
        response = self.client.post("/menu/tags/create/", data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Tag.objects.exists())
        self.assertFalse(TagLogo.objects.exists())


# ---------------------------------------------------------------------------
# Тести для DishCreateView (таски 2.6, 2.6.1)
#
# Найскладніша форма у спринті — перевіряємо:
#   1. GET: форма з FK dropdown, M2M checkboxes, image upload, formset
#   2. POST без тегів → ValidationError (clean_tags, таска 2.6.1)
#   3. POST без головного зображення → помилка (обов'язкове, таска 2.6.1)
#   4. POST з тегами + зображенням → Dish + DishMainImage створюються
#   5. POST з додатковими зображеннями → DishPicture створюються (formset)
#   6. Транзакція: все або нічого (transaction.atomic)
#
# ManagementForm:
#   Django FormSet потребує приховані поля TOTAL_FORMS та INITIAL_FORMS
#   у кожному POST-запиті. Без них Django кине ManagementForm data is missing.
#   У тестах ми додаємо їх вручну: "pictures-TOTAL_FORMS": "0"
#   Документація:
#     https://docs.djangoproject.com/en/stable/topics/forms/formsets/#understanding-the-managementform
# ---------------------------------------------------------------------------
class DishCreateTest(TestCase):
    """Test the dish creation form at /menu/dishes/create/.

    Перевіряємо що DishCreateView коректно обробляє:
    FK (category), M2M (tags, мінімум 1), обов'язкове головне зображення,
    та formset для додаткових зображень. Все в transaction.atomic().
    """

    cat: Category
    tag1: Tag
    tag2: Tag

    @classmethod
    def setUpTestData(cls) -> None:
        """Create shared test data for all test methods."""
        cls.cat = Category.objects.create(
            title="Салати", description="Свіжі салати", number_in_line=1
        )
        cls.tag1 = Tag.objects.create(
            title="Веган", description="Без тваринних продуктів"
        )
        cls.tag2 = Tag.objects.create(title="Гостре", description="Гострі страви")

    # --- Приховані поля ManagementForm для порожнього formset --- #
    # Кожен FormSet потребує TOTAL_FORMS та INITIAL_FORMS у POST-даних.
    # "0" — жодних додаткових зображень.
    EMPTY_FORMSET: dict[str, str] = {
        "pictures-TOTAL_FORMS": "0",
        "pictures-INITIAL_FORMS": "0",
    }

    def _dish_data(self, **overrides: object) -> dict[str, object]:
        """Return valid dish form data with all required fields.

        Включає:
        - Основні поля (title, description, price, weight, calorie)
        - category (FK, обов'язкове)
        - tags (M2M, мінімум 1 — clean_tags)
        - main_image (обов'язкове — image_form)
        - ManagementForm для порожнього formset
        """
        data: dict[str, object] = {
            "title": "Грецький салат",
            "description": "Класичний грецький салат з фетою",
            "price": "11.50",
            "weight": 350,
            "calorie": 280,
            "category": self.cat.pk,
            "tags": [self.tag1.pk],
            # --- Головне зображення (обов'язкове) --- #
            "main_image-title": "Фото страви",
            "main_image-image": self._make_image(),
            # --- ManagementForm для порожнього formset --- #
            **self.EMPTY_FORMSET,
        }
        data.update(overrides)
        return data

    def _make_image(self, name: str = "dish.jpg") -> SimpleUploadedFile:
        """Create a minimal valid JPEG file for testing."""
        jpeg_bytes = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
            b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
            b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
            b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
            b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
            b"\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04"
            b"\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07"
            b"\x22q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16"
            b"\x17\x18\x19\x1a%&'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83"
            b"\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a"
            b"\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8"
            b"\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6"
            b"\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2"
            b"\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa"
            b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00T\xdb\xae\x8a(\x03\xff\xd9"
        )
        return SimpleUploadedFile(name, jpeg_bytes, content_type="image/jpeg")

    # --- GET тести --- #

    def test_create_form_get(self) -> None:
        """GET /menu/dishes/create/ повинен показати порожню форму."""
        response = self.client.get("/menu/dishes/create/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<form")
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_create_form_uses_correct_template(self) -> None:
        """View повинна рендерити шаблон menu/dish_form.html."""
        response = self.client.get("/menu/dishes/create/")
        self.assertTemplateUsed(response, "menu/dish_form.html")

    def test_create_form_has_enctype(self) -> None:
        """Форма повинна мати enctype="multipart/form-data" для файлів."""
        response = self.client.get("/menu/dishes/create/")
        self.assertContains(response, 'enctype="multipart/form-data"')

    def test_create_form_has_category_select(self) -> None:
        """Форма повинна містити <select> з категоріями (FK dropdown)."""
        response = self.client.get("/menu/dishes/create/")
        self.assertContains(response, "Салати")
        self.assertContains(response, "form-select")

    def test_create_form_has_tag_checkboxes(self) -> None:
        """Форма повинна містити checkboxes для тегів (M2M)."""
        response = self.client.get("/menu/dishes/create/")
        self.assertContains(response, "Веган")
        self.assertContains(response, "Гостре")
        self.assertContains(response, 'type="checkbox"')

    def test_create_form_has_image_section(self) -> None:
        """GET повинен показати секцію головного зображення (обов'язкове)."""
        response = self.client.get("/menu/dishes/create/")
        self.assertContains(response, "Головне зображення")
        self.assertContains(response, 'name="main_image-title"')
        self.assertContains(response, 'name="main_image-image"')

    def test_create_form_has_picture_formset(self) -> None:
        """GET повинен показати секцію додаткових зображень (formset).

        FormSet рендерить ManagementForm (приховані поля TOTAL_FORMS тощо)
        та extra=1 порожню форму для завантаження зображення.
        """
        response = self.client.get("/menu/dishes/create/")
        self.assertContains(response, "Додаткові зображення")
        # ManagementForm — приховані поля
        self.assertContains(response, "pictures-TOTAL_FORMS")
        # prefix="pictures" — поля першої форми
        self.assertContains(response, 'name="pictures-0-title"')
        self.assertContains(response, 'name="pictures-0-image"')

    def test_create_form_has_add_picture_button(self) -> None:
        """GET повинен показати кнопку "Додати ще зображення".

        JavaScript використовує цю кнопку для клонування порожньої форми
        та оновлення TOTAL_FORMS у ManagementForm.
        """
        response = self.client.get("/menu/dishes/create/")
        self.assertContains(response, "add-picture-btn")
        self.assertContains(response, "Додати ще зображення")

    # --- POST тести: валідація обов'язкових полів (таска 2.6.1) --- #

    def test_create_dish_without_tags_fails(self) -> None:
        """POST без тегів → помилка clean_tags(), Dish не створюється.

        clean_tags() (таска 2.6.1) перевіряє що M2M-список не порожній.
        tags має blank=True у моделі, але форма вимагає мінімум 1 тег.
        """
        data = self._dish_data()
        del data["tags"]
        response = self.client.post("/menu/dishes/create/", data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Dish.objects.exists())

    def test_create_dish_without_image_fails(self) -> None:
        """POST без головного зображення → помилка, Dish не створюється.

        Головне зображення обов'язкове (таска 2.6.1):
        form_valid() додає add_error("image", ...) якщо файл не завантажено.
        """
        data = self._dish_data()
        del data["main_image-image"]
        response = self.client.post("/menu/dishes/create/", data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Dish.objects.exists())
        self.assertFalse(DishMainImage.objects.exists())

    def test_create_dish_post_invalid_title(self) -> None:
        """POST з невалідними даними → форма з помилками, без редиректу."""
        response = self.client.post("/menu/dishes/create/", self._dish_data(title=""))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Dish.objects.exists())

    # --- POST тести: успішне створення --- #

    def test_create_dish_post_valid(self) -> None:
        """POST з усіма обов'язковими полями → створює Dish → redirect.

        Обов'язкові поля (таска 2.6.1):
        - category (FK), tags (M2M, мін. 1), main_image (ImageField)
        """
        response = self.client.post("/menu/dishes/create/", self._dish_data())
        self.assertRedirects(response, "/menu/dishes/")
        self.assertTrue(Dish.objects.filter(title="Грецький салат").exists())
        self.assertTrue(DishMainImage.objects.exists())

    def test_create_dish_with_two_tags(self) -> None:
        """POST з двома тегами → обидва M2M зв'язки зберігаються."""
        data = self._dish_data(tags=[self.tag1.pk, self.tag2.pk])
        response = self.client.post("/menu/dishes/create/", data)
        self.assertRedirects(response, "/menu/dishes/")

        dish = Dish.objects.get(title="Грецький салат")
        self.assertIn(self.tag1, dish.tags.all())
        self.assertIn(self.tag2, dish.tags.all())
        self.assertEqual(dish.tags.count(), 2)

    # --- POST тести: додаткові зображення (formset, таска 2.6.1) --- #

    def test_create_dish_with_additional_pictures(self) -> None:
        """POST з додатковими зображеннями → DishPicture створюються.

        FormSet обробляє N форм, кожна з яких створює DishPicture.
        formset.instance = dish зв'язує кожен DishPicture з Dish.
        Порожні форми у formset автоматично пропускаються.
        """
        data = self._dish_data()
        # Замінюємо порожній formset на formset з 2 зображеннями
        data["pictures-TOTAL_FORMS"] = "2"
        data["pictures-0-title"] = "Додаткове фото 1"
        data["pictures-0-image"] = self._make_image("extra1.jpg")
        data["pictures-1-title"] = "Додаткове фото 2"
        data["pictures-1-image"] = self._make_image("extra2.jpg")
        response = self.client.post("/menu/dishes/create/", data)
        self.assertRedirects(response, "/menu/dishes/")

        dish = Dish.objects.get(title="Грецький салат")
        # Перевіряємо що 2 додаткових зображення створені та зв'язані
        self.assertEqual(dish.additional_images.count(), 2)

    def test_create_dish_without_additional_pictures(self) -> None:
        """POST без додаткових зображень → Dish створюється без DishPicture."""
        response = self.client.post("/menu/dishes/create/", self._dish_data())
        self.assertRedirects(response, "/menu/dishes/")
        self.assertTrue(Dish.objects.exists())
        self.assertFalse(DishPicture.objects.exists())

    # --- POST тести: інтеграційний (все разом) --- #

    def test_create_dish_full(self) -> None:
        """POST з усіма полями: FK + M2M + зображення + formset → все зберігається.

        Інтеграційний тест: перевіряємо що всі зв'язки та форми
        працюють разом в одному запиті, загорнутому в transaction.atomic().
        """
        data = self._dish_data(tags=[self.tag1.pk, self.tag2.pk])
        data["pictures-TOTAL_FORMS"] = "1"
        data["pictures-0-title"] = "Додаткове"
        data["pictures-0-image"] = self._make_image("extra.jpg")
        response = self.client.post("/menu/dishes/create/", data)
        self.assertRedirects(response, "/menu/dishes/")

        dish = Dish.objects.get(title="Грецький салат")
        # FK — категорія
        self.assertEqual(dish.category, self.cat)
        # M2M — теги
        self.assertEqual(dish.tags.count(), 2)
        # OneToOne — головне зображення
        self.assertTrue(DishMainImage.objects.filter(dish=dish).exists())
        # ForeignKey (reverse) — додаткові зображення
        self.assertEqual(dish.additional_images.count(), 1)


# ---------------------------------------------------------------------------
# Тести для TagUpdateView (таска 2.7)
#
# UpdateView — generic view для редагування існуючого об'єкта.
# Перевіряємо:
#   - GET /menu/tags/<pk>/edit/ — форма заповнена поточними даними
#   - POST з валідними даними → оновлення тега → redirect
#   - Оновлення тега з додаванням нового логотипу
#   - Оновлення тега з заміною існуючого логотипу
#   - Оновлення тега без зміни логотипу (тільки текстові поля)
#
# Документація:
#   https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-editing/#updateview
# ---------------------------------------------------------------------------
class TagUpdateTest(TestCase):
    """Test tag editing at /menu/tags/<pk>/edit/.

    UpdateView завантажує існуючий об'єкт, показує заповнену форму,
    і при POST оновлює запис у БД (UPDATE замість INSERT).
    """

    tag: Tag

    @classmethod
    def setUpTestData(cls) -> None:
        """Create a test tag for update tests."""
        cls.tag = Tag.objects.create(
            title="Веган", description="Без тваринних продуктів"
        )

    def _make_svg(self, name: str = "logo.svg") -> SimpleUploadedFile:
        """Create a minimal valid SVG file for testing."""
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
        return SimpleUploadedFile(name, svg_content, content_type="image/svg+xml")

    def _url(self) -> str:
        """Return the URL for editing the test tag."""
        return f"/menu/tags/{self.tag.pk}/edit/"

    # --- GET тести --- #

    def test_update_form_get(self) -> None:
        """GET /menu/tags/<pk>/edit/ повинен повертати HTTP 200."""
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    def test_update_form_uses_correct_template(self) -> None:
        """UpdateView перевикористовує шаблон tag_form.html."""
        response = self.client.get(self._url())
        self.assertTemplateUsed(response, "menu/tag_form.html")

    def test_update_form_prefilled(self) -> None:
        """GET показує форму з поточними даними тега.

        UpdateView автоматично заповнює форму через instance=tag.
        У HTML це означає <input value="Веган">.
        """
        response = self.client.get(self._url())
        self.assertContains(response, "Веган")
        self.assertContains(response, "Без тваринних продуктів")

    def test_update_form_shows_edit_title(self) -> None:
        """Заголовок сторінки — "Редагувати тег" (не "Створити").

        Шаблон перевіряє form.instance.pk: якщо pk є — це update.
        """
        response = self.client.get(self._url())
        self.assertContains(response, "Редагувати тег")

    def test_update_form_has_logo_section(self) -> None:
        """GET повинен показати секцію логотипу."""
        response = self.client.get(self._url())
        self.assertContains(response, "Логотип тега")
        self.assertContains(response, 'name="logo-title"')

    # --- POST тести --- #

    def test_update_tag_post_valid(self) -> None:
        """POST з валідними даними → тег оновлюється → redirect.

        form.save() викликає UPDATE замість INSERT, бо instance.pk існує.
        """
        data = {"title": "Вегетаріанське", "description": "Без м'яса"}
        response = self.client.post(self._url(), data)
        self.assertRedirects(response, "/menu/tags/")

        self.tag.refresh_from_db()
        self.assertEqual(self.tag.title, "Вегетаріанське")
        self.assertEqual(self.tag.description, "Без м'яса")

    def test_update_tag_post_invalid(self) -> None:
        """POST з порожнім title → помилка валідації, тег не змінюється."""
        data = {"title": "", "description": "Опис"}
        response = self.client.post(self._url(), data)
        self.assertEqual(response.status_code, 200)

        self.tag.refresh_from_db()
        self.assertEqual(self.tag.title, "Веган")

    def test_update_tag_add_logo(self) -> None:
        """POST з логотипом до тега без логотипу → TagLogo створюється.

        Тег раніше не мав логотипу, після update — має.
        """
        data = {
            "title": "Веган",
            "description": "Без тваринних продуктів",
            "logo-title": "Іконка вегана",
            "logo-image": self._make_svg(),
        }
        response = self.client.post(self._url(), data)
        self.assertRedirects(response, "/menu/tags/")
        self.assertTrue(TagLogo.objects.filter(tag=self.tag).exists())

    def test_update_tag_replace_logo(self) -> None:
        """POST з новим логотипом до тега з існуючим → логотип оновлюється.

        instance=existing_logo → Django оновлює (UPDATE) замість створення
        нового TagLogo. Кількість логотипів залишається 1.
        """
        # Спочатку створюємо логотип
        TagLogo.objects.create(tag=self.tag, title="Стара іконка", image="old.svg")

        data = {
            "title": "Веган",
            "description": "Без тваринних продуктів",
            "logo-title": "Нова іконка",
            "logo-image": self._make_svg("new.svg"),
        }
        response = self.client.post(self._url(), data)
        self.assertRedirects(response, "/menu/tags/")

        # Логотип оновлений, а не дубльований
        self.assertEqual(TagLogo.objects.filter(tag=self.tag).count(), 1)
        self.tag.refresh_from_db()
        self.assertEqual(self.tag.logo.title, "Нова іконка")

    def test_update_tag_without_changing_logo(self) -> None:
        """POST без файлу логотипу → тег оновлюється, логотип не змінюється.

        Якщо користувач не завантажує файл, has_logo=False і логіка
        збереження логотипу пропускається.
        """
        TagLogo.objects.create(tag=self.tag, title="Іконка", image="existing.svg")

        data = {"title": "Веган оновлений", "description": "Нове"}
        response = self.client.post(self._url(), data)
        self.assertRedirects(response, "/menu/tags/")

        self.tag.refresh_from_db()
        self.assertEqual(self.tag.title, "Веган оновлений")
        # Логотип залишився
        self.assertTrue(TagLogo.objects.filter(tag=self.tag).exists())

    def test_update_nonexistent_tag_returns_404(self) -> None:
        """GET для неіснуючого pk → HTTP 404.

        UpdateView автоматично повертає 404, якщо об'єкт не знайдено.
        """
        response = self.client.get("/menu/tags/99999/edit/")
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Тести для category_update FBV (таска 2.7)
#
# FBV-підхід до update — порівняння з TagUpdateView (CBV):
#   FBV: if/else + render(), instance=category у формі
#   CBV: Django обробляє GET/POST автоматично, перевизначення методів
#
# Перевіряємо ті самі кейси що й для TagUpdateView:
#   - GET: форма заповнена поточними даними
#   - POST: оновлення тексту, додавання/заміна логотипу
#   - 404 для неіснуючого pk
# ---------------------------------------------------------------------------
class CategoryUpdateTest(TestCase):
    """Test category editing at /menu/categories/<pk>/edit/.

    FBV category_update — аналогічний до category_create, але з instance.
    Перевикористовує шаблон category_form.html.
    """

    cat: Category

    @classmethod
    def setUpTestData(cls) -> None:
        """Create a test category for update tests."""
        cls.cat = Category.objects.create(
            title="Салати", description="Свіжі салати", number_in_line=1
        )

    def _make_svg(self, name: str = "logo.svg") -> SimpleUploadedFile:
        """Create a minimal valid SVG file for testing."""
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
        return SimpleUploadedFile(name, svg_content, content_type="image/svg+xml")

    def _url(self) -> str:
        """Return the URL for editing the test category."""
        return f"/menu/categories/{self.cat.pk}/edit/"

    # --- GET тести --- #

    def test_update_form_get(self) -> None:
        """GET /menu/categories/<pk>/edit/ повинен повертати HTTP 200."""
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    def test_update_form_uses_correct_template(self) -> None:
        """FBV перевикористовує шаблон category_form.html."""
        response = self.client.get(self._url())
        self.assertTemplateUsed(response, "menu/category_form.html")

    def test_update_form_prefilled(self) -> None:
        """GET показує форму з поточними даними категорії."""
        response = self.client.get(self._url())
        self.assertContains(response, "Салати")
        self.assertContains(response, "Свіжі салати")

    def test_update_form_shows_edit_title(self) -> None:
        """Заголовок сторінки — "Редагувати категорію" (не "Створити")."""
        response = self.client.get(self._url())
        self.assertContains(response, "Редагувати категорію")

    # --- POST тести --- #

    def test_update_category_post_valid(self) -> None:
        """POST з валідними даними → категорія оновлюється → redirect."""
        data = {"title": "Десерти", "description": "Солодощі", "number_in_line": 5}
        response = self.client.post(self._url(), data)
        self.assertRedirects(response, "/menu/categories/")

        self.cat.refresh_from_db()
        self.assertEqual(self.cat.title, "Десерти")
        self.assertEqual(self.cat.number_in_line, 5)

    def test_update_category_post_invalid(self) -> None:
        """POST з порожнім title → помилка валідації."""
        data = {"title": "", "description": "Опис", "number_in_line": 1}
        response = self.client.post(self._url(), data)
        self.assertEqual(response.status_code, 200)

        self.cat.refresh_from_db()
        self.assertEqual(self.cat.title, "Салати")

    def test_update_category_add_logo(self) -> None:
        """POST з логотипом → CategoryLogo створюється."""
        data = {
            "title": "Салати",
            "description": "Свіжі салати",
            "number_in_line": 1,
            "logo-title": "Іконка салатів",
            "logo-image": self._make_svg(),
        }
        response = self.client.post(self._url(), data)
        self.assertRedirects(response, "/menu/categories/")
        self.assertTrue(CategoryLogo.objects.filter(category=self.cat).exists())

    def test_update_category_replace_logo(self) -> None:
        """POST з новим логотипом → існуючий логотип оновлюється."""
        CategoryLogo.objects.create(
            category=self.cat, title="Стара іконка", image="old.svg"
        )

        data = {
            "title": "Салати",
            "description": "Свіжі салати",
            "number_in_line": 1,
            "logo-title": "Нова іконка",
            "logo-image": self._make_svg("new.svg"),
        }
        response = self.client.post(self._url(), data)
        self.assertRedirects(response, "/menu/categories/")

        self.assertEqual(CategoryLogo.objects.filter(category=self.cat).count(), 1)
        self.cat.refresh_from_db()
        self.assertEqual(self.cat.logo.title, "Нова іконка")

    def test_update_category_without_changing_logo(self) -> None:
        """POST без файлу → категорія оновлюється, логотип залишається."""
        CategoryLogo.objects.create(
            category=self.cat, title="Іконка", image="existing.svg"
        )

        data = {"title": "Салати оновлені", "description": "Нове", "number_in_line": 2}
        response = self.client.post(self._url(), data)
        self.assertRedirects(response, "/menu/categories/")

        self.cat.refresh_from_db()
        self.assertEqual(self.cat.title, "Салати оновлені")
        self.assertTrue(CategoryLogo.objects.filter(category=self.cat).exists())

    def test_update_nonexistent_category_returns_404(self) -> None:
        """GET для неіснуючого pk → HTTP 404."""
        response = self.client.get("/menu/categories/99999/edit/")
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Тести для DishUpdateView (таска 2.7)
#
# Найскладніший update — FK + M2M + головне зображення + formset.
# Перевіряємо:
#   - GET: форма заповнена поточними даними (category, tags, image)
#   - POST: оновлення тексту без зміни зображення
#   - POST: заміна головного зображення
#   - POST: збереження M2M (тегів)
#   - 404 для неіснуючого pk
# ---------------------------------------------------------------------------
class DishUpdateTest(TestCase):
    """Test dish editing at /menu/dishes/<pk>/edit/.

    DishUpdateView — найскладніший update view: FK, M2M, зображення, formset.
    Перевикористовує dish_form.html.
    """

    cat: Category
    tag1: Tag
    tag2: Tag
    dish: Dish

    @classmethod
    def setUpTestData(cls) -> None:
        """Create test data: category, tags, dish with main image."""
        cls.cat = Category.objects.create(
            title="Салати", description="Свіжі салати", number_in_line=1
        )
        cls.tag1 = Tag.objects.create(
            title="Веган", description="Без тваринних продуктів"
        )
        cls.tag2 = Tag.objects.create(title="Гостре", description="Гострі страви")
        cls.dish = Dish.objects.create(
            title="Цезар",
            description="Класичний салат",
            price=12.50,
            weight=350,
            calorie=420,
            category=cls.cat,
        )
        cls.dish.tags.add(cls.tag1)
        DishMainImage.objects.create(
            dish=cls.dish, title="Фото Цезаря", image="dish_main_images/caesar.jpg"
        )

    # --- Приховані поля ManagementForm для порожнього formset --- #
    EMPTY_FORMSET: dict[str, str] = {
        "pictures-TOTAL_FORMS": "0",
        "pictures-INITIAL_FORMS": "0",
    }

    def _make_image(self, name: str = "dish.jpg") -> SimpleUploadedFile:
        """Create a minimal valid JPEG file for testing."""
        jpeg_bytes = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
            b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
            b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
            b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
            b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
            b"\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04"
            b"\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07"
            b"\x22q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16"
            b"\x17\x18\x19\x1a%&'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83"
            b"\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a"
            b"\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8"
            b"\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6"
            b"\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2"
            b"\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa"
            b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00T\xdb\xae\x8a(\x03\xff\xd9"
        )
        return SimpleUploadedFile(name, jpeg_bytes, content_type="image/jpeg")

    def _url(self) -> str:
        """Return the URL for editing the test dish."""
        return f"/menu/dishes/{self.dish.pk}/edit/"

    def _dish_data(self, **overrides: object) -> dict[str, object]:
        """Return valid dish update data with formset management fields."""
        data: dict[str, object] = {
            "title": "Цезар",
            "description": "Класичний салат",
            "price": "12.50",
            "weight": 350,
            "calorie": 420,
            "category": self.cat.pk,
            "tags": [self.tag1.pk],
            "main_image-title": "Фото Цезаря",
            **self.EMPTY_FORMSET,
        }
        data.update(overrides)
        return data

    # --- GET тести --- #

    def test_update_form_get(self) -> None:
        """GET /menu/dishes/<pk>/edit/ повинен повертати HTTP 200."""
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    def test_update_form_uses_correct_template(self) -> None:
        """UpdateView перевикористовує шаблон dish_form.html."""
        response = self.client.get(self._url())
        self.assertTemplateUsed(response, "menu/dish_form.html")

    def test_update_form_prefilled(self) -> None:
        """GET показує форму з поточними даними страви."""
        response = self.client.get(self._url())
        self.assertContains(response, "Цезар")
        self.assertContains(response, "Класичний салат")

    def test_update_form_shows_edit_title(self) -> None:
        """Заголовок сторінки — "Редагувати страву" (не "Створити")."""
        response = self.client.get(self._url())
        self.assertContains(response, "Редагувати страву")

    # --- POST тести --- #

    def test_update_dish_text_only(self) -> None:
        """POST без нового зображення → страва оновлюється, зображення залишається.

        При update: якщо файл не завантажено, поточне зображення не змінюється.
        """
        data = self._dish_data(title="Цезар оновлений", description="Нова версія")
        response = self.client.post(self._url(), data)
        self.assertRedirects(response, "/menu/dishes/")

        self.dish.refresh_from_db()
        self.assertEqual(self.dish.title, "Цезар оновлений")
        # Зображення залишилось
        self.assertTrue(DishMainImage.objects.filter(dish=self.dish).exists())

    def test_update_dish_replace_image(self) -> None:
        """POST з новим зображенням → головне зображення оновлюється."""
        data = self._dish_data()
        data["main_image-image"] = self._make_image("new_photo.jpg")
        response = self.client.post(self._url(), data)
        self.assertRedirects(response, "/menu/dishes/")

        # Зображення оновлене (1 запис, не дубль)
        self.assertEqual(DishMainImage.objects.filter(dish=self.dish).count(), 1)

    def test_update_dish_change_tags(self) -> None:
        """POST з іншими тегами → M2M зв'язки оновлюються."""
        data = self._dish_data(tags=[self.tag2.pk])
        response = self.client.post(self._url(), data)
        self.assertRedirects(response, "/menu/dishes/")

        self.dish.refresh_from_db()
        tag_ids = list(self.dish.tags.values_list("pk", flat=True))
        self.assertEqual(tag_ids, [self.tag2.pk])

    def test_update_dish_post_invalid(self) -> None:
        """POST з порожнім title → помилка валідації."""
        data = self._dish_data(title="")
        response = self.client.post(self._url(), data)
        self.assertEqual(response.status_code, 200)

        self.dish.refresh_from_db()
        self.assertEqual(self.dish.title, "Цезар")

    def test_update_nonexistent_dish_returns_404(self) -> None:
        """GET для неіснуючого pk → HTTP 404."""
        response = self.client.get("/menu/dishes/99999/edit/")
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Тести для TagDeleteView (таска 2.7)
#
# DeleteView — два етапи:
#   1. GET — сторінка підтвердження з інформацією що буде видалено
#   2. POST — видаляє тег та пов'язані об'єкти (CASCADE)
#
# Перевіряємо:
#   - GET показує сторінку підтвердження з назвою тега
#   - POST видаляє тег та його логотип (CASCADE)
#   - POST redirect на tag_list
#   - 404 для неіснуючого pk
#
# Документація:
#   https://docs.djangoproject.com/en/stable/ref/class-based-views/generic-editing/#deleteview
# ---------------------------------------------------------------------------
class TagDeleteTest(TestCase):
    """Test tag deletion at /menu/tags/<pk>/delete/.

    DeleteView показує сторінку підтвердження (GET) і видаляє тег (POST).
    TagLogo видаляється автоматично через CASCADE.
    """

    def _make_svg(self, name: str = "logo.svg") -> SimpleUploadedFile:
        """Create a minimal valid SVG file for testing."""
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
        return SimpleUploadedFile(name, svg_content, content_type="image/svg+xml")

    # --- GET тести --- #

    def test_delete_confirmation_get(self) -> None:
        """GET /menu/tags/<pk>/delete/ показує сторінку підтвердження."""
        tag = Tag.objects.create(title="Веган", description="Тест")
        response = self.client.get(f"/menu/tags/{tag.pk}/delete/")
        self.assertEqual(response.status_code, 200)

    def test_delete_confirmation_template(self) -> None:
        """Використовується шаблон tag_confirm_delete.html."""
        tag = Tag.objects.create(title="Веган", description="Тест")
        response = self.client.get(f"/menu/tags/{tag.pk}/delete/")
        self.assertTemplateUsed(response, "menu/tag_confirm_delete.html")

    def test_delete_confirmation_shows_tag_name(self) -> None:
        """Сторінка підтвердження показує назву тега."""
        tag = Tag.objects.create(title="Веган", description="Тест")
        response = self.client.get(f"/menu/tags/{tag.pk}/delete/")
        self.assertContains(response, "Веган")

    def test_delete_confirmation_shows_logo_info(self) -> None:
        """Якщо тег має логотип — показуємо що він також буде видалений."""
        tag = Tag.objects.create(title="Веган", description="Тест")
        TagLogo.objects.create(tag=tag, title="Іконка вегана", image="test.svg")
        response = self.client.get(f"/menu/tags/{tag.pk}/delete/")
        self.assertContains(response, "Іконка вегана")

    # --- POST тести --- #

    def test_delete_tag_post(self) -> None:
        """POST → тег видаляється → redirect на tag_list."""
        tag = Tag.objects.create(title="Веган", description="Тест")
        response = self.client.post(f"/menu/tags/{tag.pk}/delete/")
        self.assertRedirects(response, "/menu/tags/")
        self.assertFalse(Tag.objects.filter(pk=tag.pk).exists())

    def test_delete_tag_cascades_logo(self) -> None:
        """POST → тег та його логотип видаляються (CASCADE).

        on_delete=CASCADE у TagLogo.tag → Django автоматично видаляє
        логотип при видаленні тега. Це каскадне видалення на рівні БД.
        """
        tag = Tag.objects.create(title="Веган", description="Тест")
        TagLogo.objects.create(tag=tag, title="Іконка", image="test.svg")

        self.client.post(f"/menu/tags/{tag.pk}/delete/")
        self.assertFalse(Tag.objects.filter(pk=tag.pk).exists())
        self.assertFalse(TagLogo.objects.exists())

    def test_delete_tag_keeps_dishes(self) -> None:
        """Видалення тега НЕ видаляє страви (M2M — лише зв'язок).

        ManyToMany: видалення одного боку видаляє запис у проміжній таблиці,
        але об'єкт на іншому боці залишається.
        """
        tag = Tag.objects.create(title="Веган", description="Тест")
        cat = Category.objects.create(title="Салати", description="Тест")
        dish = Dish.objects.create(
            title="Цезар",
            description="Тест",
            price=10,
            weight=200,
            calorie=300,
            category=cat,
        )
        dish.tags.add(tag)

        self.client.post(f"/menu/tags/{tag.pk}/delete/")
        # Тег видалений, але страва залишилась
        self.assertFalse(Tag.objects.filter(pk=tag.pk).exists())
        self.assertTrue(Dish.objects.filter(pk=dish.pk).exists())
        self.assertEqual(dish.tags.count(), 0)

    def test_delete_nonexistent_tag_returns_404(self) -> None:
        """GET для неіснуючого pk → HTTP 404."""
        response = self.client.get("/menu/tags/99999/delete/")
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Тести для CategoryDeleteView (таска 2.7)
#
# Видалення категорії — НЕБЕЗПЕЧНА операція, бо CASCADE видаляє:
#   - CategoryLogo
#   - Всі Dish у категорії
#   - DishMainImage та DishPicture кожної страви
#
# Перевіряємо:
#   - GET показує сторінку підтвердження зі списком страв
#   - POST каскадно видаляє все пов'язане
#   - Порожня категорія (без страв) — теж видаляється коректно
# ---------------------------------------------------------------------------
class CategoryDeleteTest(TestCase):
    """Test category deletion at /menu/categories/<pk>/delete/.

    Перевіряємо каскадне видалення: категорія → страви → зображення.
    Сторінка підтвердження показує список страв, що будуть видалені.
    """

    # --- GET тести --- #

    def test_delete_confirmation_get(self) -> None:
        """GET /menu/categories/<pk>/delete/ показує сторінку підтвердження."""
        cat = Category.objects.create(title="Салати", description="Тест")
        response = self.client.get(f"/menu/categories/{cat.pk}/delete/")
        self.assertEqual(response.status_code, 200)

    def test_delete_confirmation_template(self) -> None:
        """Використовується шаблон category_confirm_delete.html."""
        cat = Category.objects.create(title="Салати", description="Тест")
        response = self.client.get(f"/menu/categories/{cat.pk}/delete/")
        self.assertTemplateUsed(response, "menu/category_confirm_delete.html")

    def test_delete_confirmation_shows_category_name(self) -> None:
        """Сторінка підтвердження показує назву категорії."""
        cat = Category.objects.create(title="Салати", description="Тест")
        response = self.client.get(f"/menu/categories/{cat.pk}/delete/")
        self.assertContains(response, "Салати")

    def test_delete_confirmation_shows_dishes_list(self) -> None:
        """Сторінка підтвердження показує список страв, що будуть видалені.

        Це ключова відмінність від TagDeleteView — користувач бачить
        які саме страви загинуть разом з категорією.
        """
        cat = Category.objects.create(title="Салати", description="Тест")
        Dish.objects.create(
            title="Цезар",
            description="Тест",
            price=10,
            weight=200,
            calorie=300,
            category=cat,
        )
        Dish.objects.create(
            title="Грецький",
            description="Тест",
            price=12,
            weight=300,
            calorie=250,
            category=cat,
        )

        response = self.client.get(f"/menu/categories/{cat.pk}/delete/")
        self.assertContains(response, "Цезар")
        self.assertContains(response, "Грецький")
        self.assertContains(response, "2")  # кількість страв

    # --- POST тести --- #

    def test_delete_category_post(self) -> None:
        """POST → категорія видаляється → redirect на category_list."""
        cat = Category.objects.create(title="Салати", description="Тест")
        response = self.client.post(f"/menu/categories/{cat.pk}/delete/")
        self.assertRedirects(response, "/menu/categories/")
        self.assertFalse(Category.objects.filter(pk=cat.pk).exists())

    def test_delete_category_cascades_logo(self) -> None:
        """POST → логотип категорії видаляється (CASCADE)."""
        cat = Category.objects.create(title="Салати", description="Тест")
        CategoryLogo.objects.create(category=cat, title="Іконка", image="test.svg")

        self.client.post(f"/menu/categories/{cat.pk}/delete/")
        self.assertFalse(CategoryLogo.objects.exists())

    def test_delete_category_cascades_dishes(self) -> None:
        """POST → всі страви категорії видаляються (CASCADE).

        Dish.category має on_delete=CASCADE → Django видаляє всі страви,
        коли їхня категорія видаляється.
        """
        cat = Category.objects.create(title="Салати", description="Тест")
        Dish.objects.create(
            title="Цезар",
            description="Тест",
            price=10,
            weight=200,
            calorie=300,
            category=cat,
        )
        Dish.objects.create(
            title="Грецький",
            description="Тест",
            price=12,
            weight=300,
            calorie=250,
            category=cat,
        )

        self.client.post(f"/menu/categories/{cat.pk}/delete/")
        self.assertFalse(Dish.objects.exists())

    def test_delete_category_cascades_dish_images(self) -> None:
        """POST → зображення страв видаляються каскадно.

        Ланцюжок CASCADE: Category → Dish → DishMainImage + DishPicture.
        """
        cat = Category.objects.create(title="Салати", description="Тест")
        dish = Dish.objects.create(
            title="Цезар",
            description="Тест",
            price=10,
            weight=200,
            calorie=300,
            category=cat,
        )
        DishMainImage.objects.create(dish=dish, title="Фото", image="test.jpg")
        DishPicture.objects.create(dish=dish, title="Додаткове", image="extra.jpg")

        self.client.post(f"/menu/categories/{cat.pk}/delete/")
        self.assertFalse(DishMainImage.objects.exists())
        self.assertFalse(DishPicture.objects.exists())

    def test_delete_empty_category(self) -> None:
        """Порожня категорія (без страв) видаляється без помилок."""
        cat = Category.objects.create(title="Порожня", description="Без страв")
        response = self.client.post(f"/menu/categories/{cat.pk}/delete/")
        self.assertRedirects(response, "/menu/categories/")
        self.assertFalse(Category.objects.filter(pk=cat.pk).exists())

    def test_delete_nonexistent_category_returns_404(self) -> None:
        """GET для неіснуючого pk → HTTP 404."""
        response = self.client.get("/menu/categories/99999/delete/")
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Тести для DishDeleteView (таска 2.7)
#
# Видалення страви каскадно видаляє:
#   - DishMainImage (OneToOne, CASCADE)
#   - DishPicture (ForeignKey, CASCADE)
#   - M2M записи (Dish-Tag) — зв'язки видаляються, теги залишаються
#
# Перевіряємо:
#   - GET показує сторінку підтвердження з інформацією про зображення
#   - POST каскадно видаляє все пов'язане
#   - Теги та категорія залишаються
# ---------------------------------------------------------------------------
class DishDeleteTest(TestCase):
    """Test dish deletion at /menu/dishes/<pk>/delete/.

    Перевіряємо каскадне видалення: страва → зображення.
    Сторінка підтвердження показує інформацію про зображення.
    """

    cat: Category

    @classmethod
    def setUpTestData(cls) -> None:
        """Create shared test category."""
        cls.cat = Category.objects.create(
            title="Салати", description="Свіжі салати", number_in_line=1
        )

    def _create_dish(self) -> Dish:
        """Create a test dish with main image."""
        dish = Dish.objects.create(
            title="Цезар",
            description="Тест",
            price=10,
            weight=200,
            calorie=300,
            category=self.cat,
        )
        DishMainImage.objects.create(dish=dish, title="Фото Цезаря", image="test.jpg")
        return dish

    # --- GET тести --- #

    def test_delete_confirmation_get(self) -> None:
        """GET /menu/dishes/<pk>/delete/ показує сторінку підтвердження."""
        dish = self._create_dish()
        response = self.client.get(f"/menu/dishes/{dish.pk}/delete/")
        self.assertEqual(response.status_code, 200)

    def test_delete_confirmation_template(self) -> None:
        """Використовується шаблон dish_confirm_delete.html."""
        dish = self._create_dish()
        response = self.client.get(f"/menu/dishes/{dish.pk}/delete/")
        self.assertTemplateUsed(response, "menu/dish_confirm_delete.html")

    def test_delete_confirmation_shows_dish_name(self) -> None:
        """Сторінка підтвердження показує назву та ціну страви."""
        dish = self._create_dish()
        response = self.client.get(f"/menu/dishes/{dish.pk}/delete/")
        self.assertContains(response, "Цезар")

    def test_delete_confirmation_shows_main_image(self) -> None:
        """Сторінка підтвердження показує назву головного зображення."""
        dish = self._create_dish()
        response = self.client.get(f"/menu/dishes/{dish.pk}/delete/")
        self.assertContains(response, "Фото Цезаря")

    def test_delete_confirmation_shows_additional_images(self) -> None:
        """Сторінка підтвердження показує назви додаткових зображень."""
        dish = self._create_dish()
        DishPicture.objects.create(dish=dish, title="Додаткове 1", image="extra1.jpg")
        DishPicture.objects.create(dish=dish, title="Додаткове 2", image="extra2.jpg")

        response = self.client.get(f"/menu/dishes/{dish.pk}/delete/")
        self.assertContains(response, "Додаткове 1")
        self.assertContains(response, "Додаткове 2")

    # --- POST тести --- #

    def test_delete_dish_post(self) -> None:
        """POST → страва видаляється → redirect на dish_list."""
        dish = self._create_dish()
        response = self.client.post(f"/menu/dishes/{dish.pk}/delete/")
        self.assertRedirects(response, "/menu/dishes/")
        self.assertFalse(Dish.objects.filter(pk=dish.pk).exists())

    def test_delete_dish_cascades_main_image(self) -> None:
        """POST → головне зображення видаляється (CASCADE).

        DishMainImage.dish має on_delete=CASCADE → видаляється з Dish.
        """
        dish = self._create_dish()
        self.client.post(f"/menu/dishes/{dish.pk}/delete/")
        self.assertFalse(DishMainImage.objects.exists())

    def test_delete_dish_cascades_additional_images(self) -> None:
        """POST → додаткові зображення видаляються (CASCADE).

        DishPicture.dish має on_delete=CASCADE → всі DishPicture видаляються.
        """
        dish = self._create_dish()
        DishPicture.objects.create(dish=dish, title="Фото 1", image="extra1.jpg")
        DishPicture.objects.create(dish=dish, title="Фото 2", image="extra2.jpg")

        self.client.post(f"/menu/dishes/{dish.pk}/delete/")
        self.assertFalse(DishPicture.objects.exists())

    def test_delete_dish_keeps_category_and_tags(self) -> None:
        """Видалення страви НЕ видаляє категорію та теги.

        FK (category) — видаляється лише зв'язок, не батьківський об'єкт.
        M2M (tags) — записи у проміжній таблиці видаляються, теги залишаються.
        """
        dish = self._create_dish()
        tag = Tag.objects.create(title="Веган", description="Тест")
        dish.tags.add(tag)

        self.client.post(f"/menu/dishes/{dish.pk}/delete/")
        # Категорія і тег залишились
        self.assertTrue(Category.objects.filter(pk=self.cat.pk).exists())
        self.assertTrue(Tag.objects.filter(pk=tag.pk).exists())

    def test_delete_nonexistent_dish_returns_404(self) -> None:
        """GET для неіснуючого pk → HTTP 404."""
        response = self.client.get("/menu/dishes/99999/delete/")
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Тести для адмін-навігації та CRUD-посилань у шаблонах (таска 2.8)
#
# Перевіряємо що кнопки створення, редагування та видалення
# присутні на відповідних сторінках.
# ---------------------------------------------------------------------------
class AdminNavCrudLinksTest(TestCase):
    """Test admin navigation and CRUD links in templates (task 2.8).

    Перевіряємо наявність посилань на create/edit/delete
    у navbar та на сторінках списків.
    """

    cat: Category
    tag: Tag
    dish: Dish

    @classmethod
    def setUpTestData(cls) -> None:
        """Create test data for CRUD links tests."""
        from user.models import User

        cls.staff_user = User.objects.create_superuser(  # type: ignore[attr-defined]
            email="staff@test.com", username="stafftest", password="testpass123"
        )
        cls.cat = Category.objects.create(
            title="Салати", description="Тест", number_in_line=1
        )
        cls.tag = Tag.objects.create(title="Веган", description="Тест")
        cls.dish = Dish.objects.create(
            title="Цезар",
            description="Тест",
            price=10,
            weight=200,
            calorie=300,
            category=cls.cat,
        )
        cls.dish.tags.add(cls.tag)
        DishMainImage.objects.create(dish=cls.dish, title="Фото", image="test.jpg")

    def setUp(self) -> None:
        """Log in as staff for each test."""
        self.client.force_login(self.staff_user)  # type: ignore[attr-defined]

    # --- Navbar dropdown --- #

    def test_navbar_has_admin_dropdown(self) -> None:
        """Navbar містить dropdown з написом АДМІНІСТРУВАННЯ."""
        response = self.client.get("/menu/")
        self.assertContains(response, "АДМІНІСТРУВАННЯ")
        self.assertContains(response, "dropdown-toggle")

    def test_navbar_has_search_form(self) -> None:
        """Navbar містить форму пошуку з полем q та кнопкою."""
        response = self.client.get("/menu/")
        self.assertContains(response, 'name="q"')
        self.assertContains(response, "/menu/search/")
        self.assertContains(response, "bi-search")

    def test_navbar_has_create_links(self) -> None:
        """Dropdown містить посилання на створення category, tag, dish."""
        response = self.client.get("/menu/")
        self.assertContains(response, "/menu/categories/create/")
        self.assertContains(response, "/menu/tags/create/")
        self.assertContains(response, "/menu/dishes/create/")

    # --- Category list: edit/delete buttons --- #

    def test_category_list_has_edit_button(self) -> None:
        """Список категорій містить кнопку редагування."""
        response = self.client.get("/menu/categories/")
        self.assertContains(response, f"/menu/categories/{self.cat.pk}/edit/")

    def test_category_list_has_delete_button(self) -> None:
        """Список категорій містить кнопку видалення."""
        response = self.client.get("/menu/categories/")
        self.assertContains(response, f"/menu/categories/{self.cat.pk}/delete/")

    # --- Tag list: edit/delete buttons --- #

    def test_tag_list_has_edit_button(self) -> None:
        """Список тегів містить кнопку редагування."""
        response = self.client.get("/menu/tags/")
        self.assertContains(response, f"/menu/tags/{self.tag.pk}/edit/")

    def test_tag_list_has_delete_button(self) -> None:
        """Список тегів містить кнопку видалення."""
        response = self.client.get("/menu/tags/")
        self.assertContains(response, f"/menu/tags/{self.tag.pk}/delete/")

    # --- Dish list: edit/delete buttons --- #

    # --- Dish detail: edit/delete buttons --- #

    def test_dish_detail_has_edit_button(self) -> None:
        """Сторінка деталей страви містить кнопку редагування."""
        response = self.client.get(f"/menu/dishes/{self.dish.pk}/")
        self.assertContains(response, f"/menu/dishes/{self.dish.pk}/edit/")

    def test_dish_detail_has_delete_button(self) -> None:
        """Сторінка деталей страви містить кнопку видалення."""
        response = self.client.get(f"/menu/dishes/{self.dish.pk}/")
        self.assertContains(response, f"/menu/dishes/{self.dish.pk}/delete/")


# ---------------------------------------------------------------------------
# Тести пошуку страв (таска 3.1)
#
# Перевіряємо:
#   - Базовий GET без параметрів
#   - Пошук по назві страви (title)
#   - Пошук по опису страви (description)
#   - Пошук по назві категорії (category__title)
#   - Пошук по назві тегу (tags__title)
#   - Порожній запит — результатів немає
#   - Немає збігів — порожній список
#   - Регістронезалежний пошук (icontains)
#   - Унікальність результатів (distinct)
#
# Документація Q-objects:
#   https://docs.djangoproject.com/en/stable/topics/db/queries/#complex-lookups-with-q-objects
# ---------------------------------------------------------------------------
class DishSearchTest(TestCase):
    """Test dish search at /menu/search/?q=...

    Q-objects дозволяють будувати OR-запити по кількох полях.
    icontains забезпечує регістронезалежний пошук.
    """

    cat: Category
    tag: Tag
    dish: Dish

    @classmethod
    def setUpTestData(cls) -> None:
        """Create test data for search tests."""
        cls.cat = Category.objects.create(
            title="Салати", description="Свіжі салати", number_in_line=1
        )
        cls.tag = Tag.objects.create(title="Веганська страва", description="Без м'яса")
        cls.dish = Dish.objects.create(
            title="Вінегрет",
            description="Традиційний салат із печених овочів",
            price=5.50,
            weight=250,
            calorie=180,
            category=cls.cat,
        )
        cls.dish.tags.add(cls.tag)

    # --- Базові тести --- #

    def test_search_page_returns_200(self) -> None:
        """GET /menu/search/ без параметрів → HTTP 200."""
        response = self.client.get("/menu/search/")
        self.assertEqual(response.status_code, 200)

    def test_search_uses_correct_template(self) -> None:
        """View використовує шаблон search_results.html."""
        response = self.client.get("/menu/search/")
        self.assertTemplateUsed(response, "menu/search_results.html")

    def test_empty_query_returns_no_results(self) -> None:
        """Порожній запит (без ?q=) → порожній QuerySet.

        Пустий пошук не повинен повертати всі страви —
        це і неінтуїтивно, і може бути повільним на великій БД.
        """
        response = self.client.get("/menu/search/")
        self.assertEqual(len(response.context["dishes"]), 0)

    def test_whitespace_query_returns_no_results(self) -> None:
        """Запит з пробілів (?q=   ) → порожній QuerySet.

        strip() прибирає пробіли — запит стає порожнім.
        """
        response = self.client.get("/menu/search/", {"q": "   "})
        self.assertEqual(len(response.context["dishes"]), 0)

    # --- Пошук по різних полях (Q-objects) --- #

    def test_search_by_dish_title(self) -> None:
        """Пошук по назві страви: Q(title__icontains=query)."""
        response = self.client.get("/menu/search/", {"q": "Вінегрет"})
        self.assertContains(response, "Вінегрет")
        self.assertEqual(len(response.context["dishes"]), 1)

    def test_search_by_dish_description(self) -> None:
        """Пошук по опису: Q(description__icontains=query)."""
        response = self.client.get("/menu/search/", {"q": "печених овочів"})
        self.assertContains(response, "Вінегрет")

    # --- Регістронезалежність --- #

    def test_search_case_insensitive(self) -> None:
        """Case-insensitive search via icontains (ASCII).

        SQLite підтримує case-insensitive LIKE тільки для ASCII символів.
        Для кирилиці регістронезалежність працює лише з PostgreSQL (ILIKE).
        Тому тестуємо на ASCII: створюємо страву з латинською назвою.

        Документація:
          https://docs.djangoproject.com/en/stable/ref/models/querysets/#icontains
        """
        Dish.objects.create(
            title="Caesar Salad",
            description="Classic",
            price=10,
            weight=300,
            calorie=250,
            category=self.cat,
        )
        response = self.client.get("/menu/search/", {"q": "caesar salad"})
        self.assertEqual(len(response.context["dishes"]), 1)

    # --- Без збігів --- #

    def test_search_no_results(self) -> None:
        """Запит без збігів → порожній список."""
        response = self.client.get("/menu/search/", {"q": "Піца"})
        self.assertEqual(len(response.context["dishes"]), 0)
        self.assertContains(response, "нічого не знайдено")

    # --- distinct() --- #

    def test_search_no_duplicates(self) -> None:
        """distinct() — страва не дублюється при збігу по кількох полях.

        Якщо "салат" є і в title страви, і в category__title,
        без distinct() QuerySet поверне 2 рядки для однієї страви.
        distinct() гарантує унікальність.
        """
        # Створюємо страву де "салат" є і в назві, і в описі, і в категорії
        dish2 = Dish.objects.create(
            title="Грецький салат",
            description="Салат зі свіжих овочів та фети",
            price=8,
            weight=300,
            calorie=220,
            category=self.cat,  # Категорія "Салати"
        )
        dish2.tags.add(self.tag)

        response = self.client.get("/menu/search/", {"q": "салат"})
        dishes = response.context["dishes"]
        # Перевіряємо що кожна страва присутня лише один раз
        dish_ids = [d.pk for d in dishes]
        self.assertEqual(len(dish_ids), len(set(dish_ids)))

    # --- Контекст --- #

    def test_search_context_contains_query(self) -> None:
        """Контекст містить пошуковий запит для відображення у шаблоні."""
        response = self.client.get("/menu/search/", {"q": "тест"})
        self.assertEqual(response.context["query"], "тест")

    def test_search_results_highlight_title(self) -> None:
        """Результати пошуку містять <mark> для підсвічування збігів у назві.

        Custom фільтр |highlight обгортає збіги в <mark>...</mark>.
        Документація:
          https://docs.djangoproject.com/en/stable/howto/custom-template-tags/
        """
        response = self.client.get("/menu/search/", {"q": "Вінегрет"})
        self.assertContains(response, "<mark>Вінегрет</mark>")


# ---------------------------------------------------------------------------
# Тести для кастомного фільтру highlight (таска 3.1)
#
# Фільтр обгортає збіги пошукового запиту в <mark> теги.
# Перевіряємо:
#   - Базове підсвічування
#   - Регістронезалежність
#   - XSS-безпека (HTML-екранування)
#   - Порожні значення
#
# Документація custom template filters:
#   https://docs.djangoproject.com/en/stable/howto/custom-template-tags/#writing-custom-template-filters
# ---------------------------------------------------------------------------
class HighlightFilterTest(TestCase):
    """Test the |highlight custom template filter.

    Фільтр highlight обгортає збіги в <mark> теги
    з захистом від XSS через escape().
    """

    def test_basic_highlight(self) -> None:
        """Базове підсвічування: збіг обгортається в <mark>."""
        result = highlight("Борщ український", "Борщ")
        self.assertEqual(result, "<mark>Борщ</mark> український")

    def test_case_insensitive_highlight(self) -> None:
        """Регістронезалежне підсвічування (re.IGNORECASE)."""
        result = highlight("Caesar Salad", "caesar")
        self.assertEqual(result, "<mark>Caesar</mark> Salad")

    def test_multiple_matches(self) -> None:
        """Всі збіги підсвічуються, не лише перший."""
        result = highlight("салат з салатом", "салат")
        self.assertEqual(result, "<mark>салат</mark> з <mark>салат</mark>ом")

    def test_xss_prevention(self) -> None:
        """HTML в тексті екранується для запобігання XSS.

        escape() перетворює <script> у &lt;script&gt; ПЕРЕД
        додаванням <mark> тегів.
        """
        result = highlight("<script>alert('xss')</script>", "script")
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;", result)
        self.assertIn("<mark>", result)

    def test_empty_query(self) -> None:
        """Порожній запит — повертає оригінальний текст без змін."""
        result = highlight("Борщ", "")
        self.assertEqual(result, "Борщ")

    def test_empty_text(self) -> None:
        """Порожній текст — повертає порожній рядок."""
        result = highlight("", "борщ")
        self.assertEqual(result, "")

    def test_special_regex_chars(self) -> None:
        """Спеціальні символи regex (., *, +) обробляються коректно.

        re.escape() екранує спеціальні символи у запиті.
        """
        result = highlight("ціна 10.50 грн", "10.50")
        self.assertEqual(result, "ціна <mark>10.50</mark> грн")
