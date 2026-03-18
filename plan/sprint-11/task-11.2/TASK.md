# Task 11.2 — Форма відгуку (post-delivery)

## Мета

Після отримання замовлення відвідувач бачить форму з emoji-кнопками настрою та полем для повідомлення.

## Що робити

### 1. View

```python
# feedback/views.py

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext_lazy as _

from feedback.services import create_feedback
from orders.models import Order
from orders.services import can_access_order


def submit_feedback(request: HttpRequest, order_id: int) -> HttpResponse:
    """Visitor submits feedback for a delivered order (POST only)."""
    order = get_object_or_404(Order, pk=order_id)
    if not can_access_order(request, order):
        return HttpResponse(status=403)

    if request.method == "POST":
        mood = request.POST.get("mood", "")
        message = request.POST.get("message", "")
        visitor_name = request.POST.get("visitor_name", "")
        try:
            create_feedback(order, mood=mood, message=message, visitor_name=visitor_name)
            messages.success(request, _("Дякуємо за відгук! 🙏"))
        except ValueError as e:
            messages.warning(request, str(e))

    return redirect("orders:order_detail", order_id=order_id)
```

### 2. URL

```python
# feedback/urls.py

from django.urls import path
from feedback.views import submit_feedback, feedback_board

app_name = "feedback"

urlpatterns = [
    path("<int:order_id>/submit/", submit_feedback, name="submit"),
    path("board/", feedback_board, name="board"),
]
```

```python
# core_settings/urls.py — додати
path("feedback/", include("feedback.urls")),
```

### 3. Template: форма на order_detail

```html
<!-- templates/orders/order_detail.html — після tracker, коли status == 'delivered' -->

{% if order.status == 'delivered' and not has_feedback %}
<div class="card mt-4 border-success" id="feedback-form">
  <div class="card-body text-center">
    <h5>{% trans "Як вам сподобалось?" %}</h5>
    <form method="post" action="{% url 'feedback:submit' order.id %}">
      {% csrf_token %}

      <!-- Emoji mood selector -->
      <div class="mood-selector mb-3">
        {% for value, label in mood_choices %}
        <label class="mood-option">
          <input type="radio" name="mood" value="{{ value }}"
                 class="d-none" {% if forloop.first %}checked{% endif %}>
          <span class="mood-emoji" data-mood="{{ value }}">
            {{ label }}
          </span>
        </label>
        {% endfor %}
      </div>

      <!-- Optional name -->
      <div class="mb-3">
        <input type="text" name="visitor_name" class="form-control"
               maxlength="50"
               placeholder="{% trans "Ваше ім'я (необов'язково)" %}">
      </div>

      <!-- Optional message -->
      <div class="mb-3">
        <textarea name="message" class="form-control" rows="2"
                  maxlength="500"
                  placeholder="{% trans 'Напишіть щось приємне... або корисне 😊' %}"></textarea>
      </div>

      <button type="submit" class="btn btn-success btn-action">
        {% trans "Надіслати відгук" %}
      </button>
    </form>
  </div>
</div>

{% elif has_feedback %}
<div class="alert alert-success mt-4 text-center">
  <strong>{% trans "Дякуємо за відгук!" %}</strong> {{ feedback.get_mood_display }}
  {% if feedback.message %}
    <br><em>"{{ feedback.message|truncatechars:100 }}"</em>
  {% endif %}
</div>
{% endif %}
```

### 4. CSS: mood selector

```css
/* staticfiles/css/brand.css */

.mood-selector {
    display: flex;
    justify-content: center;
    gap: 0.5rem;
    flex-wrap: wrap;
}

.mood-option {
    cursor: pointer;
}

.mood-emoji {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.5rem 1rem;
    border: 2px solid var(--bs-border-color);
    border-radius: 2rem;
    font-size: 1.1rem;
    transition: all 0.2s;
    min-height: 48px; /* touch-friendly */
}

.mood-option input:checked + .mood-emoji {
    border-color: var(--bs-success);
    background: var(--bs-success-bg-subtle);
    transform: scale(1.1);
}

.mood-emoji:hover {
    border-color: var(--bs-primary);
}
```

### 5. JS: mood selection UX

```javascript
// Inline або окремий файл
document.querySelectorAll('.mood-option input').forEach(radio => {
    radio.addEventListener('change', () => {
        document.querySelectorAll('.mood-emoji').forEach(el => {
            el.style.transform = '';
            el.style.borderColor = '';
        });
        const selected = radio.nextElementSibling;
        selected.style.transform = 'scale(1.1)';
    });
});
```

### 6. Context для order_detail

```python
# orders/views.py — order_detail, додати в context:

from feedback.models import GuestFeedback

feedback = None
has_feedback = False
try:
    feedback = order.feedback
    has_feedback = True
except GuestFeedback.DoesNotExist:
    pass

context = {
    ...
    "has_feedback": has_feedback,
    "feedback": feedback,
    "mood_choices": GuestFeedback.Mood.choices if not has_feedback else [],
}
```

## Тести

### Tier 2

```python
@pytest.mark.tier2
@pytest.mark.django_db
class TestFeedbackForm:
    def test_form_visible_for_delivered(self, client, delivered_order):
        """Feedback form appears on delivered order detail."""
        response = client.get(f"/order/{order.id}/detail/?token={order.access_token}")
        assert b'mood-selector' in response.content

    def test_form_hidden_for_non_delivered(self, client, approved_order):
        """No feedback form for non-delivered orders."""
        response = client.get(f"/order/{order.id}/detail/?token={order.access_token}")
        assert b'mood-selector' not in response.content

    def test_submit_creates_feedback(self, client, delivered_order):
        """POST creates feedback and redirects."""
        response = client.post(f"/feedback/{order.id}/submit/", {
            "mood": "love", "message": "Чудовий борщ!",
        })
        assert response.status_code == 302
        assert GuestFeedback.objects.filter(order=order).exists()

    def test_duplicate_rejected(self, client, order_with_feedback):
        """Second feedback submission shows warning."""
        response = client.post(f"/feedback/{order.id}/submit/", {"mood": "good"})
        # Should redirect with warning, not create duplicate
        assert GuestFeedback.objects.filter(order=order).count() == 1

    def test_confirmation_shown_after_submit(self, client, order_with_feedback):
        """After submitting, order_detail shows confirmation instead of form."""
        response = client.get(f"/order/{order.id}/detail/?token={order.access_token}")
        assert b'mood-selector' not in response.content
        assert 'Дякуємо' in response.content.decode()
```

## Оцінка: 2 години

## Acceptance Criteria

- [ ] Форма з'являється тільки для delivered замовлень
- [ ] Emoji-кнопки настрою (touch-friendly, 48px)
- [ ] Ім'я та повідомлення — необов'язкові
- [ ] POST створює feedback, redirect з flash message
- [ ] Після submit — показується confirmation замість форми
- [ ] Дублікат — warning, не error
- [ ] Тести зелені
