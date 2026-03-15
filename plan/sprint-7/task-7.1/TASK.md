# Task 7.1 — Mobile-first верстка: visitor menu і cart (детально)

## Принципи

- Bootstrap 5 grid — `col-12 col-md-6 col-lg-4` для карток страв
- Touch targets: кнопки "В кошик" — мінімум `min-height: 48px`
- Sticky header з language switcher і кошиком
- Фото страв — lazy loading, обрізані квадратно

## staticfiles/css/visitor.css

```css
/* Mobile-first базові стилі для відвідувача */
:root {
    --primary: #e34c26;       /* фестивальний червоний */
    --bg: #1a1a1a;            /* темний фон (сонце → читабельніше) */
    --surface: #2a2a2a;
    --text: #f0f0f0;
    --muted: #999;
    --success: #28a745;
    --warning: #ffc107;
}

body {
    background: var(--bg);
    color: var(--text);
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 16px;  /* не менше 16px — запобігає zoom на iOS */
}

/* Touch targets */
.btn {
    min-height: 48px;
    min-width: 48px;
    font-size: 1rem;
    padding: 12px 20px;
}

.btn-lg {
    min-height: 56px;
    font-size: 1.1rem;
}

/* Картка страви */
.dish-card {
    background: var(--surface);
    border-radius: 12px;
    overflow: hidden;
    margin-bottom: 16px;
}

.dish-card img {
    width: 100%;
    height: 180px;
    object-fit: cover;
    display: block;
}

.dish-card .dish-info {
    padding: 12px 16px;
}

.dish-card h3 {
    font-size: 1.1rem;
    margin: 0 0 8px;
    line-height: 1.3;
}

.dish-card .price {
    font-size: 1.3rem;
    font-weight: bold;
    color: var(--primary);
}

.dish-card .dish-description {
    font-size: 0.875rem;
    color: var(--muted);
    margin: 4px 0 12px;
    line-height: 1.4;
}

/* Sticky header */
.site-header {
    position: sticky;
    top: 0;
    z-index: 100;
    background: var(--bg);
    border-bottom: 1px solid #333;
    padding: 8px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.cart-badge {
    position: relative;
    display: inline-block;
}

.cart-badge .count {
    position: absolute;
    top: -8px;
    right: -8px;
    background: var(--primary);
    color: white;
    border-radius: 50%;
    width: 20px;
    height: 20px;
    font-size: 0.75rem;
    display: flex;
    align-items: center;
    justify-content: center;
}

/* Кошик — фіксована кнопка внизу */
.cart-fab {
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 200;
    border-radius: 28px;
    padding: 16px 24px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.4);
    font-size: 1rem;
    font-weight: bold;
}

/* Кількість у кошику — inline input + кнопки */
.quantity-control {
    display: flex;
    align-items: center;
    gap: 8px;
}

.quantity-control input {
    width: 56px;
    text-align: center;
    font-size: 1.1rem;
    padding: 8px 4px;
}

/* Алергени */
.allergen-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(255, 193, 7, 0.15);
    border: 1px solid rgba(255, 193, 7, 0.4);
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.75rem;
    margin: 2px;
}

/* Низька наявність */
.availability-low {
    border-left: 3px solid var(--warning);
}
```

## templates/orders/visitor_menu.html

```html
{% extends "base_visitor.html" %}
{% load i18n %}

{% block content %}
<div class="container-fluid px-3">

    <!-- Категорії — горизонтальний скрол -->
    <div class="category-nav d-flex gap-2 py-3 overflow-x-auto">
        {% for category in categories %}
        <a href="#cat-{{ category.id }}"
           class="btn btn-outline-secondary btn-sm text-nowrap">
            {{ category.title }}
        </a>
        {% endfor %}
    </div>

    <!-- Страви по категоріях -->
    {% for category in categories %}
    <section id="cat-{{ category.id }}" class="mb-4">
        <h2 class="h5 py-2 border-bottom">{{ category.title }}</h2>
        <div class="row g-3">
            {% for dish in category.dishes.all %}
            {% if dish.availability != 'out' %}
            <div class="col-12 col-sm-6 col-lg-4">
                {% include "orders/dish_card.html" with dish=dish %}
            </div>
            {% endif %}
            {% endfor %}
        </div>
    </section>
    {% endfor %}

</div>

<!-- FAB кнопка кошика -->
{% if cart_count > 0 %}
<a href="{% url 'orders:cart' %}" class="btn btn-primary cart-fab">
    🛒 {% trans "Кошик" %} ({{ cart_count }})
</a>
{% endif %}
{% endblock %}
```

## templates/base_visitor.html

```html
<!DOCTYPE html>
<html lang="{{ LANGUAGE_CODE }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
    <meta name="theme-color" content="#e34c26">
    <title>🇺🇦 Festival Menu</title>
    <link rel="manifest" href="/static/manifest.json">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3/dist/css/bootstrap.min.css">
    {% load static %}
    <link rel="stylesheet" href="{% static 'css/visitor.css' %}">
</head>
<body>
<header class="site-header">
    <span class="fw-bold">🇺🇦 Festival</span>
    {% include "partials/language_switcher.html" %}
    <a href="{% url 'orders:cart' %}" class="cart-badge">
        🛒
        {% if cart_count > 0 %}
        <span class="count">{{ cart_count }}</span>
        {% endif %}
    </a>
</header>

<main>
    {% if messages %}
    <div class="px-3 pt-2">
        {% for message in messages %}
        <div class="alert alert-{{ message.tags }} alert-dismissible py-2 mb-2">
            {{ message }}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    {% block content %}{% endblock %}
</main>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
```

## Context processor для cart_count

```python
# orders/context_processors.py
from django.http import HttpRequest
from orders.cart import cart_item_count


def cart_context(request: HttpRequest) -> dict[str, int]:
    return {"cart_count": cart_item_count(request)}
```

```python
# settings/base.py — додати до TEMPLATES context_processors
"orders.context_processors.cart_context",
```

## Тести

```python
# orders/tests/test_mobile_ui.py
import pytest


@pytest.mark.tier2
@pytest.mark.django_db
def test_visitor_menu_has_viewport_meta(client):
    response = client.get("/order/menu/")
    content = response.content.decode()
    assert "viewport" in content
    assert "width=device-width" in content


@pytest.mark.tier2
@pytest.mark.django_db
def test_cart_count_in_context(client):
    from menu.models import Category, Dish
    from decimal import Decimal

    cat = Category.objects.create(
        title_uk="C", title_en="C", description_uk="", description_en="", number_in_line=1
    )
    dish = Dish.objects.create(
        title_uk="D", title_en="D", description_uk="", description_en="",
        price=Decimal("5.00"), weight=100, calorie=100,
        category=cat, availability="available",
    )
    session = client.session
    session["festival_cart"] = [{"dish_id": dish.id, "quantity": 3}]
    session.save()

    response = client.get("/order/menu/")
    assert response.context["cart_count"] == 3


@pytest.mark.tier1
def test_visitor_css_exists():
    import os
    css_path = os.path.join("staticfiles", "css", "visitor.css")
    assert os.path.exists(css_path)
```

## Acceptance criteria

- [ ] `visitor.css` — темна тема, touch targets ≥ 48px
- [ ] `base_visitor.html` — viewport meta, manifest link
- [ ] `cart_context` context processor — `cart_count` доступний у всіх visitor шаблонах
- [ ] FAB кнопка кошика — фіксована внизу, видна коли кошик не порожній
- [ ] Категорії — горизонтальний скрол без wrap
- [ ] Тести зелені
