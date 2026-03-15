# Task 7.2 — Mobile-first: kitchen і waiter dashboards (детально)

## staticfiles/css/staff.css

```css
/* Staff (kitchen/waiter) — мобільний інтерфейс для роботи в полі */
:root {
    --pending-color: #ffc107;
    --taken-color: #17a2b8;
    --done-color: #28a745;
    --danger-color: #dc3545;
}

/* Тікет кухні — картка з великою кнопкою дії */
.ticket-card {
    background: #2a2a2a;
    border-radius: 10px;
    padding: 14px;
    margin-bottom: 12px;
    border-left: 4px solid var(--pending-color);
}

.ticket-card.status-taken {
    border-left-color: var(--taken-color);
}

.ticket-card.status-done {
    border-left-color: var(--done-color);
}

.ticket-card.escalated {
    border-left-color: var(--danger-color);
    animation: pulse-border 2s infinite;
}

@keyframes pulse-border {
    0%, 100% { border-left-color: var(--danger-color); }
    50% { border-left-color: #ff6b6b; }
}

.ticket-dish-name {
    font-size: 1.1rem;
    font-weight: bold;
    margin: 0 0 4px;
}

.ticket-meta {
    font-size: 0.8rem;
    color: #aaa;
    margin-bottom: 10px;
}

.ticket-action-btn {
    width: 100%;
    min-height: 52px;
    font-size: 1rem;
    font-weight: bold;
    border-radius: 8px;
}

/* Секції дашборду — collapsible на мобільному */
.dashboard-section {
    margin-bottom: 20px;
}

.dashboard-section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 0;
    border-bottom: 1px solid #444;
    cursor: pointer;
}

.section-count-badge {
    background: var(--pending-color);
    color: #000;
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 0.85rem;
    font-weight: bold;
}

/* Waiter — картка замовлення */
.order-card {
    background: #2a2a2a;
    border-radius: 10px;
    margin-bottom: 16px;
    overflow: hidden;
}

.order-card-header {
    padding: 12px 16px;
    background: #333;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.order-card.order-ready {
    border: 2px solid var(--done-color);
}

.order-card.order-ready .order-card-header {
    background: rgba(40, 167, 69, 0.2);
}

.order-items-list {
    padding: 8px 16px;
}

.order-item-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
    border-bottom: 1px solid #3a3a3a;
}

.order-item-row:last-child {
    border-bottom: none;
}

.item-status-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 8px;
}

.item-status-dot.pending { background: var(--pending-color); }
.item-status-dot.taken { background: var(--taken-color); }
.item-status-dot.done { background: var(--done-color); }

/* Connection indicator */
.connection-status {
    position: fixed;
    top: 8px;
    right: 8px;
    z-index: 1000;
    font-size: 0.75rem;
    padding: 2px 8px;
    border-radius: 12px;
}
```

## templates/base_staff.html

```html
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
    <meta name="theme-color" content="#1a1a1a">
    <title>{% block title %}Festival Staff{% endblock %}</title>
    <link rel="manifest" href="/static/manifest.json">
    <link rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/bootstrap@5.3/dist/css/bootstrap.min.css">
    {% load static %}
    <link rel="stylesheet" href="{% static 'css/staff.css' %}">
    <link rel="stylesheet" href="{% static 'css/visitor.css' %}">
</head>
<body style="background:#1a1a1a; color:#f0f0f0">

<!-- Live indicator -->
<span id="connection-indicator" class="connection-status badge bg-success">● Live</span>

<header class="site-header">
    <span class="fw-bold">
        {% block header_title %}Festival Staff{% endblock %}
    </span>
    <div class="d-flex gap-2 align-items-center">
        <span id="escalation-badge" class="badge bg-danger" style="display:none">⚠</span>
        <a href="{% url 'user:profile' %}" class="btn btn-sm btn-outline-secondary">
            {{ user.get_full_name|default:user.email }}
        </a>
    </div>
</header>

<!-- Flash container -->
<div id="flash-container" class="px-3 pt-2"></div>

<main class="container-fluid px-3 py-3">
    {% if messages %}
    {% for message in messages %}
    <div class="alert alert-{{ message.tags }} alert-dismissible py-2 mb-2">
        {{ message }}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    </div>
    {% endfor %}
    {% endif %}

    {% block content %}{% endblock %}
</main>

<!-- Кнопка ручного оновлення (fallback якщо SSE відвалилось) -->
<div class="text-center py-3">
    <button onclick="location.reload()"
            class="btn btn-sm btn-outline-secondary">
        🔄 Оновити
    </button>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3/dist/js/bootstrap.bundle.min.js"></script>
{% load static %}
<script src="{% static 'js/sse_client.js' %}"></script>
</body>
</html>
```

## templates/kitchen/dashboard.html (мобільна версія)

```html
{% extends "base_staff.html" %}
{% load i18n %}

{% block header_title %}🍳 Кухня{% endblock %}

{% block content %}

<!-- Pending секція -->
<div class="dashboard-section">
    <div class="dashboard-section-header"
         data-bs-toggle="collapse"
         data-bs-target="#section-pending">
        <span>⏳ Очікують</span>
        <span class="section-count-badge" id="pending-count">
            {{ pending|length }}
        </span>
    </div>
    <div id="section-pending" class="collapse show">
        {% for ticket in pending %}
        <div class="ticket-card {% if ticket.escalation_level > 0 %}escalated{% endif %}"
             data-ticket-id="{{ ticket.id }}">
            <p class="ticket-dish-name">{{ ticket.order_item.dish.title }}</p>
            <p class="ticket-meta">
                К-сть: {{ ticket.order_item.quantity }} •
                Офіціант: {{ ticket.order_item.order.waiter.get_full_name|default:"—" }} •
                #{{ ticket.order_item.order.id }}
            </p>
            <form method="post" action="{% url 'kitchen:ticket_take' ticket.id %}">
                {% csrf_token %}
                <button type="submit" class="btn btn-warning ticket-action-btn">
                    ▶ Взяти в роботу
                </button>
            </form>
        </div>
        {% empty %}
        <p class="text-muted text-center py-3">Немає очікуючих страв</p>
        {% endfor %}
    </div>
</div>

<!-- My taken секція -->
<div class="dashboard-section">
    <div class="dashboard-section-header"
         data-bs-toggle="collapse"
         data-bs-target="#section-taken">
        <span>👨‍🍳 Готую</span>
        <span class="section-count-badge" style="background: var(--taken-color); color: white">
            {{ my_taken|length }}
        </span>
    </div>
    <div id="section-taken" class="collapse show">
        {% for ticket in my_taken %}
        <div class="ticket-card status-taken" data-ticket-id="{{ ticket.id }}">
            <p class="ticket-dish-name">{{ ticket.order_item.dish.title }}</p>
            <p class="ticket-meta">
                К-сть: {{ ticket.order_item.quantity }} •
                Офіціант: {{ ticket.order_item.order.waiter.get_full_name|default:"—" }}
            </p>
            <form method="post" action="{% url 'kitchen:ticket_done' ticket.id %}">
                {% csrf_token %}
                <button type="submit" class="btn btn-success ticket-action-btn">
                    ✓ Готово!
                </button>
            </form>
        </div>
        {% empty %}
        <p class="text-muted text-center py-3">Немає страв в роботі</p>
        {% endfor %}
    </div>
</div>

{% endblock %}
```

## Тести

```python
# tests/test_mobile_staff.py
import pytest


@pytest.mark.tier2
@pytest.mark.django_db
def test_kitchen_dashboard_has_viewport_meta(client, django_user_model):
    kitchen = django_user_model.objects.create_user(
        email="k@test.com", password="pass", role="kitchen"
    )
    client.force_login(kitchen)
    response = client.get("/kitchen/")
    content = response.content.decode()
    assert "width=device-width" in content


@pytest.mark.tier2
@pytest.mark.django_db
def test_waiter_dashboard_has_viewport_meta(client, django_user_model):
    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
    )
    client.force_login(waiter)
    response = client.get("/order/waiter/dashboard/")
    content = response.content.decode()
    assert "width=device-width" in content


@pytest.mark.tier1
def test_staff_css_exists():
    import os
    assert os.path.exists(os.path.join("staticfiles", "css", "staff.css"))
```

## Acceptance criteria

- [ ] `staff.css` — темна тема, ticket cards з кольоровими border-left
- [ ] `base_staff.html` — viewport meta, connection indicator, SSE script
- [ ] Kitchen dashboard: 3 секції (pending, taken, done) collapsible
- [ ] Кнопки "Взяти" і "Готово" — `width:100%`, `min-height:52px`
- [ ] Escalated тікети — пульсуючий червоний border
- [ ] Тести зелені
