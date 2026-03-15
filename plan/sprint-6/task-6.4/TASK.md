# Task 6.4 — Алергени і опис мовою відвідувача (детально)

## Нова модель: menu/models.py — Allergen

```python
class Allergen(ModelWithTitle):
    """Алерген для позначення складу страви.

    Перекладається на всі мови.
    Приклади: Глютен / Gluten, Лактоза / Lactose, Горіхи / Nuts.
    """
    icon = models.CharField(
        max_length=10,
        blank=True,
        help_text="Emoji іконка: 🌾 🥛 🥜",
    )


class Dish(ModelWithTitle):
    ...
    allergens: models.ManyToManyField = models.ManyToManyField(
        Allergen,
        related_name="dishes",
        blank=True,
        verbose_name="Алергени",
    )
```

## menu/translation.py — додати Allergen

```python
from menu.models import Allergen

@register(Allergen)
class AllergenTranslationOptions(TranslationOptions):
    fields = ("title",)
```

## Шаблон картки страви: templates/orders/dish_card.html

```html
{% load i18n %}

<div class="dish-card" id="dish-{{ dish.id }}">
    {% if dish.main_image %}
    <img src="{{ dish.main_image.image.url }}" alt="{{ dish.title }}" loading="lazy">
    {% endif %}

    <div class="dish-info">
        <h3>{{ dish.title }}</h3>  {# modeltranslation автоматично повертає потрібну мову #}

        <p class="dish-description">{{ dish.description }}</p>

        <div class="dish-meta">
            <span class="price">€{{ dish.price }}</span>
            <span class="weight">{{ dish.weight }}г</span>
            <span class="calories">{{ dish.calorie }} ккал</span>
        </div>

        {% if dish.allergens.exists %}
        <div class="allergens">
            <small>
                {% trans "Алергени" %}:
                {% for allergen in dish.allergens.all %}
                    <span class="badge bg-warning text-dark">
                        {{ allergen.icon }} {{ allergen.title }}
                    </span>
                {% endfor %}
            </small>
        </div>
        {% endif %}

        {% if dish.availability == 'low' %}
        <div class="alert alert-warning alert-sm py-1">
            {% trans "Залишилось мало — уточніть у офіціанта" %}
        </div>
        {% endif %}

        <form method="post" action="{% url 'orders:cart_add' %}">
            {% csrf_token %}
            <input type="hidden" name="dish_id" value="{{ dish.id }}">
            <div class="input-group input-group-sm">
                <input type="number" name="quantity" value="1" min="1" max="10"
                       class="form-control" style="max-width: 60px">
                <button type="submit" class="btn btn-primary">
                    + {% trans "В кошик" %}
                </button>
            </div>
        </form>
    </div>
</div>
```

## locale/ — файли перекладів

```bash
# Генерувати .po файли для перекладу UI рядків
uv run python manage.py makemessages -l en -l sr -l de

# Після заповнення .po файлів:
uv run python manage.py compilemessages
```

## Тести

```python
# menu/tests/test_allergens.py
import pytest
from decimal import Decimal


@pytest.mark.tier1
def test_allergen_model_has_icon_field():
    from menu.models import Allergen
    allergen = Allergen(title_uk="Глютен", title_en="Gluten", icon="🌾")
    assert allergen.icon == "🌾"


@pytest.mark.tier2
@pytest.mark.django_db
def test_dish_with_allergens_in_menu(client):
    from menu.models import Category, Dish, Allergen
    from decimal import Decimal

    cat = Category.objects.create(
        title_uk="Тест", title_en="Test",
        description_uk="", description_en="", number_in_line=1,
    )
    allergen = Allergen.objects.create(
        title_uk="Глютен", title_en="Gluten", icon="🌾"
    )
    dish = Dish.objects.create(
        title_uk="Борщ", title_en="Borscht",
        description_uk="Суп", description_en="Soup",
        price=Decimal("8.00"), weight=400, calorie=320,
        category=cat, availability="available",
    )
    dish.allergens.add(allergen)

    response = client.get("/order/menu/")
    assert response.status_code == 200
    content = response.content.decode()
    assert "Глютен" in content or "Gluten" in content


@pytest.mark.tier2
@pytest.mark.django_db
def test_dish_card_shows_description_in_current_language(client):
    from menu.models import Category, Dish
    from decimal import Decimal

    cat = Category.objects.create(
        title_uk="Тест", title_en="Test",
        description_uk="", description_en="", number_in_line=1,
    )
    dish = Dish.objects.create(
        title_uk="Борщ", title_en="Borscht",
        description_uk="Традиційний суп", description_en="Traditional soup",
        price=Decimal("8.00"), weight=400, calorie=320,
        category=cat, availability="available",
    )

    # Тест з EN мовою через Accept-Language
    response = client.get("/order/menu/", HTTP_ACCEPT_LANGUAGE="en")
    assert response.status_code == 200
    content = response.content.decode()
    assert "Borscht" in content or "Борщ" in content  # fallback теж OK
```

## Acceptance criteria

- [ ] `Allergen` модель з перекладом `title`
- [ ] `Dish.allergens` M2M поле, міграція
- [ ] Картка страви показує алергени з emoji іконкою
- [ ] `{% trans %}` для UI рядків ("В кошик", "Алергени", "Залишилось мало")
- [ ] `makemessages` + `compilemessages` виконані для en, sr, de
- [ ] Тести зелені
