# Task 10.4 — Staff UI: отримання і resolve ескалації

## Мета

Офіціант, старший офіціант, менеджер бачать ескалації на своїх dashboards, можуть acknowledge і resolve.

## Що робити

### 1. Waiter dashboard — блок ескалацій

```html
<!-- templates/orders/waiter_dashboard.html — новий блок зверху -->

{% if my_escalations %}
<div class="alert alert-warning mb-3">
  <h5>⚠️ {% trans "Звернення відвідувачів" %} ({{ my_escalations|length }})</h5>
  {% for esc in my_escalations %}
  <div class="card mb-2 {% if esc.status == 'open' %}border-warning{% endif %}">
    <div class="card-body py-2">
      <div class="d-flex justify-content-between align-items-center">
        <div>
          <strong>{% trans "Замовлення" %} #{{ esc.order_id }}</strong>
          {% if esc.order.location_hint %}
            <span class="text-muted small">📍 {{ esc.order.location_hint }}</span>
          {% endif %}
          <br>
          <span class="text-muted">{{ esc.get_reason_display }}</span>
          {% if esc.message %} — {{ esc.message|truncatechars:60 }}{% endif %}
        </div>
        <div class="btn-group">
          {% if esc.status == 'open' %}
          <form method="post" action="{% url 'waiter:escalation_acknowledge' esc.pk %}" class="d-inline">
            {% csrf_token %}
            <button class="btn btn-sm btn-outline-primary btn-action">👁️ {% trans "Побачив" %}</button>
          </form>
          {% endif %}
          <form method="post" action="{% url 'waiter:escalation_resolve' esc.pk %}" class="d-inline">
            {% csrf_token %}
            <input type="hidden" name="note" value="">
            <button class="btn btn-sm btn-success btn-action">✅ {% trans "Вирішено" %}</button>
          </form>
        </div>
      </div>
    </div>
  </div>
  {% endfor %}
</div>
{% endif %}
```

### 2. Views

```python
# orders/waiter_views.py

@role_required(*WAITER_ROLES)
@require_POST
def escalation_acknowledge(request, escalation_id):
    escalation = get_object_or_404(VisitorEscalation, pk=escalation_id)
    try:
        acknowledge_escalation(escalation, request.user)
        messages.success(request, _("Звернення позначено як побачене."))
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("waiter:dashboard")


@role_required(*WAITER_ROLES)
@require_POST
def escalation_resolve(request, escalation_id):
    escalation = get_object_or_404(VisitorEscalation, pk=escalation_id)
    note = request.POST.get("note", "")
    try:
        resolve_escalation(escalation, request.user, note=note)
        messages.success(request, _("Звернення вирішено."))
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("waiter:dashboard")
```

### 3. URLs

```python
# orders/waiter_urls.py
path("escalation/<int:escalation_id>/ack/", escalation_acknowledge, name="escalation_acknowledge"),
path("escalation/<int:escalation_id>/resolve/", escalation_resolve, name="escalation_resolve"),
```

### 4. Dashboard context

```python
# orders/waiter_views.py — waiter_dashboard

my_escalations = VisitorEscalation.objects.filter(
    order__waiter=request.user,
    status__in=["open", "acknowledged"],
).select_related("order").order_by("created_at")

# Для senior/manager — ескалації відповідного рівня
```

### 5. Senior waiter dashboard — ескалації рівня 2+

В `senior_waiter_dashboard` додати окремий блок для ескалацій рівня SENIOR і вище.

### 6. SSE: live notification на dashboard

```javascript
// В sse_client.js (waiter SSE handler):
case 'visitor_escalation':
    // Показати toast/badge
    showEscalationAlert(data.order_id, data.reason);
    break;
```

Badge на navbar з кількістю відкритих ескалацій (опціонально).

### 7. Звуковий сигнал (опціонально)

При отриманні `visitor_escalation` — короткий звук для привернення уваги.

```javascript
const escalationSound = new Audio('/static/sounds/notification.mp3');
// Або Web Audio API beep
```

## Тести

### Tier 2

```python
@pytest.mark.tier2
@pytest.mark.django_db
class TestEscalationStaffUI:
    def test_waiter_sees_escalation(self, waiter_client, escalation): ...
    def test_acknowledge_changes_status(self, waiter_client, escalation): ...
    def test_resolve_changes_status(self, waiter_client, escalation): ...
    def test_resolved_not_shown_on_dashboard(self, waiter_client, resolved_esc): ...
    def test_senior_sees_level2_escalations(self, senior_client, level2_esc): ...
```

## Оцінка: 2 години

## Acceptance Criteria

- [ ] Waiter dashboard показує відкриті ескалації зверху
- [ ] Кнопки "Побачив" і "Вирішено" працюють
- [ ] Senior/manager бачать ескалації відповідного рівня
- [ ] SSE оновлює відвідувача при acknowledge/resolve
- [ ] Вирішені ескалації зникають з dashboard
- [ ] Тести зелені
