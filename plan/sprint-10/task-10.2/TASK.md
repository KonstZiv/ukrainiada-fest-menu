# Task 10.2 — Visitor UI: кнопка "Є проблема" + вибір причини

## Мета

Відвідувач на `order_detail` бачить кнопку ескалації (з'являється через ESCALATION_MIN_WAIT) і може обрати причину + написати коментар.

## Що робити

### 1. View

```python
# orders/views.py

def create_escalation_view(request, order_id):
    """Visitor creates an escalation (POST only)."""
    order = get_object_or_404(Order, pk=order_id)
    if not can_access_order(request, order):
        return HttpResponse(status=403)

    if request.method == "POST":
        reason = request.POST.get("reason", "")
        message = request.POST.get("message", "")
        try:
            create_escalation(order, reason=reason, message=message)
            messages.success(request, _("Ваше звернення надіслано! Ми вже працюємо."))
        except ValueError as e:
            messages.warning(request, str(e))
        return redirect("orders:order_detail", order_id=order_id)

    return redirect("orders:order_detail", order_id=order_id)
```

**URL:**
```python
path("<int:order_id>/escalate/", create_escalation_view, name="escalate"),
```

### 2. Template: кнопка + modal

```html
<!-- templates/orders/order_detail.html — після tracker -->

{% if show_escalation_button %}
<div class="text-center mt-4">
  <button class="btn btn-outline-warning btn-action"
          data-bs-toggle="modal"
          data-bs-target="#escalationModal">
    ⚠️ {% trans "Є проблема з замовленням" %}
  </button>
</div>

<!-- Modal -->
<div class="modal fade" id="escalationModal" tabindex="-1">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">{% trans "Що сталося?" %}</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <form method="post" action="{% url 'orders:escalate' order.id %}">
        {% csrf_token %}
        <div class="modal-body">
          <div class="mb-3">
            <label class="form-label">{% trans "Причина" %}</label>
            <div class="d-grid gap-2">
              {% for value, label in escalation_reasons %}
              <label class="btn btn-outline-secondary text-start">
                <input type="radio" name="reason" value="{{ value }}" class="me-2"
                       {% if forloop.first %}checked{% endif %}>
                {{ label }}
              </label>
              {% endfor %}
            </div>
          </div>
          <div class="mb-3">
            <label for="esc-message" class="form-label">
              {% trans "Коментар (необов'язково)" %}
            </label>
            <textarea id="esc-message" name="message"
                      class="form-control" rows="2" maxlength="300"
                      placeholder="{% trans 'Опишіть ситуацію...' %}"></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
            {% trans "Скасувати" %}
          </button>
          <button type="submit" class="btn btn-warning">
            ⚠️ {% trans "Надіслати" %}
          </button>
        </div>
      </form>
    </div>
  </div>
</div>
{% endif %}

{% if active_escalation %}
<div class="alert alert-info mt-3" id="escalation-status">
  <strong>{% trans "Ваше звернення:" %}</strong>
  {{ active_escalation.get_reason_display }}
  {% if active_escalation.status == 'acknowledged' %}
    — <span class="text-success">{% trans "побачено, працюємо" %}</span>
  {% elif active_escalation.status == 'open' %}
    — <span class="text-warning">{% trans "надіслано" %}</span>
  {% endif %}
</div>
{% endif %}
```

### 3. Context для template

```python
# orders/views.py — order_detail

from orders.models import VisitorEscalation

now = timezone.now()
can_escalate = (
    order.status in ("approved", "in_progress", "ready")
    and order.approved_at
    and (now - order.approved_at).total_seconds() > settings.ESCALATION_MIN_WAIT * 60
)
active_escalation = VisitorEscalation.objects.filter(
    order=order, status__in=["open", "acknowledged"],
).first()

context = {
    ...
    "show_escalation_button": can_escalate and not active_escalation,
    "active_escalation": active_escalation,
    "escalation_reasons": VisitorEscalation.Reason.choices,
}
```

### 4. JS: SSE оновлення ескалації

```javascript
// В OrderTracker.handleEvent():
case 'escalation_acknowledged':
    this.updateEscalationStatus('acknowledged', data.by);
    break;
case 'escalation_resolved':
    this.updateEscalationStatus('resolved', data.note);
    break;
```

### 5. Touch-friendly

Кнопка "Є проблема" — `btn-action` (48px min-height).
Radio buttons в modal — великі, легко тапати.
Textarea — `rows="2"`, достатньо для короткого коментаря.

## Тести

### Tier 2

```python
@pytest.mark.tier2
@pytest.mark.django_db
class TestEscalationUI:
    def test_button_hidden_before_min_wait(self, client, fresh_order): ...
    def test_button_visible_after_min_wait(self, client, old_order): ...
    def test_post_creates_escalation(self, client, old_order): ...
    def test_active_escalation_shown(self, client, escalated_order): ...
    def test_button_hidden_when_active(self, client, escalated_order): ...
```

## Оцінка: 2 години

## Acceptance Criteria

- [ ] Кнопка "Є проблема" з'являється через ESCALATION_MIN_WAIT
- [ ] Modal з вибором причини (radio) + коментар (textarea)
- [ ] POST створює ескалацію, redirect з flash message
- [ ] Активна ескалація відображається замість кнопки
- [ ] SSE оновлює статус ескалації (acknowledged → resolved)
- [ ] Touch-friendly (48px targets)
- [ ] Тести зелені
