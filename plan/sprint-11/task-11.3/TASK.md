# Task 11.3 — Публічна дошка + модерація

## Мета

Публічна сторінка з опублікованими відгуками. Менеджер модерує через admin або окремий view.

## Що робити

### 1. Public board view

```python
# feedback/views.py

from feedback.services import get_public_feedback


def feedback_board(request: HttpRequest) -> HttpResponse:
    """Public feedback board — shows published guest feedback."""
    feedbacks = get_public_feedback(limit=50)
    return render(request, "feedback/board.html", {"feedbacks": feedbacks})
```

### 2. Template: дошка

```html
<!-- templates/feedback/board.html -->
{% extends "base.html" %}
{% load i18n %}

{% block title %}{% trans "Дошка відгуків" %} — Ukrainiada{% endblock %}

{% block content %}
<div class="container-fluid mt-3">
  <h2 class="text-center mb-4">
    💬 {% trans "Що кажуть наші гості" %}
  </h2>

  {% if not feedbacks %}
  <p class="text-center text-muted">{% trans "Поки що відгуків немає. Будьте першим!" %}</p>
  {% endif %}

  <div class="feedback-grid">
    {% for fb in feedbacks %}
    <div class="feedback-card {% if fb.is_featured %}featured{% endif %}">
      <div class="feedback-mood">{{ fb.get_mood_display }}</div>
      {% if fb.message %}
        <p class="feedback-message">{{ fb.message }}</p>
      {% endif %}
      <div class="feedback-meta">
        {% if fb.visitor_name %}
          <span class="feedback-author">— {{ fb.visitor_name }}</span>
        {% endif %}
        <span class="feedback-date text-muted">
          {{ fb.created_at|timesince }} {% trans "тому" %}
        </span>
      </div>
    </div>
    {% endfor %}
  </div>
</div>
{% endblock %}
```

### 3. CSS: feedback grid

```css
/* staticfiles/css/brand.css */

.feedback-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1rem;
    max-width: 900px;
    margin: 0 auto;
}

@media (min-width: 768px) {
    .feedback-grid { grid-template-columns: 1fr 1fr; }
}

@media (min-width: 992px) {
    .feedback-grid { grid-template-columns: 1fr 1fr 1fr; }
}

.feedback-card {
    background: var(--bs-body-bg);
    border: 1px solid var(--bs-border-color);
    border-radius: 1rem;
    padding: 1.25rem;
    transition: transform 0.2s;
}

.feedback-card.featured {
    border-color: var(--bs-warning);
    background: var(--bs-warning-bg-subtle);
    grid-column: span 1;
}

@media (min-width: 768px) {
    .feedback-card.featured { grid-column: span 2; }
}

.feedback-mood {
    font-size: 1.5rem;
    margin-bottom: 0.5rem;
}

.feedback-message {
    font-style: italic;
    font-size: 1rem;
    line-height: 1.5;
    margin-bottom: 0.5rem;
}

.feedback-meta {
    font-size: 0.85rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.feedback-author {
    font-weight: 500;
}

/* Анімація для нових (якщо SSE) */
.feedback-card.new {
    animation: slideInUp 0.5s ease-out;
}

@keyframes slideInUp {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}
```

### 4. Модерація: manager view

Окрема сторінка для менеджера (додатково до admin):

```python
# feedback/views.py

from user.decorators import role_required

@role_required("manager")
def moderate_feedback(request: HttpRequest) -> HttpResponse:
    """Manager moderation view — list unpublished feedback."""
    pending = GuestFeedback.objects.filter(is_published=False).order_by("-created_at")
    published = GuestFeedback.objects.filter(is_published=True).order_by("-created_at")[:20]
    return render(request, "feedback/moderate.html", {
        "pending": pending,
        "published": published,
    })


@role_required("manager")
@require_POST
def moderate_action(request: HttpRequest, feedback_id: int) -> HttpResponse:
    """Publish, feature, or reject feedback."""
    fb = get_object_or_404(GuestFeedback, pk=feedback_id)
    action = request.POST.get("action", "")

    if action == "publish":
        publish_feedback(fb)
        messages.success(request, _("Відгук опубліковано."))
    elif action == "feature":
        feature_feedback(fb)
        messages.success(request, _("Відгук виділено і опубліковано."))
    elif action == "reject":
        fb.delete()
        messages.info(request, _("Відгук видалено."))

    return redirect("feedback:moderate")
```

```python
# feedback/urls.py — додати
path("moderate/", moderate_feedback, name="moderate"),
path("moderate/<int:feedback_id>/", moderate_action, name="moderate_action"),
```

### 5. Template: модерація

```html
<!-- templates/feedback/moderate.html -->
{% extends "base.html" %}
{% load i18n %}

{% block content %}
<div class="container mt-3">
  <h2>{% trans "Модерація відгуків" %}</h2>

  <h4>{% trans "Очікують модерації" %} ({{ pending|length }})</h4>
  {% for fb in pending %}
  <div class="card mb-2">
    <div class="card-body">
      <div class="d-flex justify-content-between">
        <div>
          <span class="fs-4">{{ fb.get_mood_display }}</span>
          {% if fb.visitor_name %}<strong>{{ fb.visitor_name }}</strong>{% endif %}
          — {% trans "Замовлення" %} #{{ fb.order_id }}
          <br>
          {% if fb.message %}
            <em>{{ fb.message }}</em>
          {% else %}
            <span class="text-muted">{% trans "(без повідомлення)" %}</span>
          {% endif %}
        </div>
        <div class="btn-group-vertical">
          <form method="post" action="{% url 'feedback:moderate_action' fb.pk %}" class="d-inline">
            {% csrf_token %}
            <input type="hidden" name="action" value="publish">
            <button class="btn btn-sm btn-success mb-1">✅ {% trans "Опублікувати" %}</button>
          </form>
          <form method="post" action="{% url 'feedback:moderate_action' fb.pk %}" class="d-inline">
            {% csrf_token %}
            <input type="hidden" name="action" value="feature">
            <button class="btn btn-sm btn-warning mb-1">⭐ {% trans "Виділити" %}</button>
          </form>
          <form method="post" action="{% url 'feedback:moderate_action' fb.pk %}" class="d-inline">
            {% csrf_token %}
            <input type="hidden" name="action" value="reject">
            <button class="btn btn-sm btn-outline-danger">🗑️ {% trans "Видалити" %}</button>
          </form>
        </div>
      </div>
    </div>
  </div>
  {% empty %}
  <p class="text-muted">{% trans "Нових відгуків немає." %}</p>
  {% endfor %}
</div>
{% endblock %}
```

### 6. Лінк на дошку

В `_navbar.html` — посилання на дошку (видиме для всіх):
```html
<a class="nav-link" href="{% url 'feedback:board' %}">💬 {% trans "Відгуки" %}</a>
```

### 7. "Великий екран" mode (optional)

Якщо дошку показуватимуть на великому екрані фестивалю — авто-скрол + авто-оновлення:

```javascript
// Опціонально, може бути GET-параметр ?kiosk=1
if (new URLSearchParams(window.location.search).get('kiosk')) {
    setInterval(() => window.location.reload(), 30000); // refresh кожні 30с
    // Або SSE для live-feed
}
```

## Тести

### Tier 2

```python
@pytest.mark.tier2
@pytest.mark.django_db
class TestFeedbackBoard:
    def test_board_shows_published_only(self, client):
        """Public board shows only is_published=True."""
        ...

    def test_board_featured_first(self, client):
        """Featured feedback appears before regular."""
        ...

    def test_board_empty_state(self, client):
        """Empty board shows friendly message."""
        ...

class TestFeedbackModeration:
    def test_manager_can_publish(self, manager_client, pending_feedback):
        """POST action=publish sets is_published=True."""
        ...

    def test_manager_can_feature(self, manager_client, pending_feedback):
        """POST action=feature sets both flags."""
        ...

    def test_manager_can_reject(self, manager_client, pending_feedback):
        """POST action=reject deletes feedback."""
        ...

    def test_non_manager_403(self, waiter_client):
        """Non-manager cannot access moderation."""
        ...
```

## Оцінка: 2.5 години

## Acceptance Criteria

- [ ] `/feedback/board/` — публічна, без авторизації
- [ ] Показує тільки `is_published=True`
- [ ] Featured виділені візуально і йдуть першими
- [ ] Responsive grid (1→2→3 колонки)
- [ ] Manager view для модерації (publish / feature / reject)
- [ ] Лінк на дошку в navbar
- [ ] Тести зелені
