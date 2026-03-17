# Task 9.4 — Візуальний timeline прогресу замовлення

## Мета

Горизонтальний (desktop) / вертикальний (mobile) progress bar, що показує загальний стан замовлення: Прийнято → Готується → Готово → Доставляється.

## Що робити

### 1. Order-level progress bar

```html
<!-- templates/orders/order_detail.html — над списком страв -->

<div class="order-progress" data-status="{{ order.status }}">
  <div class="progress-step {% if order.status != 'draft' %}done{% endif %}">
    <span class="step-icon">📝</span>
    <span class="step-label d-none d-md-inline">{% trans "Створено" %}</span>
  </div>
  <div class="progress-line"></div>
  <div class="progress-step {% if order.status in 'approved,in_progress,ready,delivered' %}done{% elif order.status == 'submitted' %}active{% endif %}">
    <span class="step-icon">👍</span>
    <span class="step-label d-none d-md-inline">{% trans "Прийнято" %}</span>
  </div>
  <div class="progress-line"></div>
  <div class="progress-step {% if order.status in 'ready,delivered' %}done{% elif order.status == 'in_progress' %}active{% endif %}">
    <span class="step-icon">👩‍🍳</span>
    <span class="step-label d-none d-md-inline">{% trans "Готується" %}</span>
  </div>
  <div class="progress-line"></div>
  <div class="progress-step {% if order.status == 'delivered' %}done{% elif order.status == 'ready' %}active{% endif %}">
    <span class="step-icon">✅</span>
    <span class="step-label d-none d-md-inline">{% trans "Готово" %}</span>
  </div>
  <div class="progress-line"></div>
  <div class="progress-step {% if order.status == 'delivered' %}done{% endif %}">
    <span class="step-icon">🍽️</span>
    <span class="step-label d-none d-md-inline">{% trans "Доставлено" %}</span>
  </div>
</div>
```

### 2. CSS

```css
/* brand.css */

.order-progress {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0;
    padding: 1rem 0;
    margin-bottom: 1rem;
}

.progress-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 48px;
}

.step-icon {
    font-size: 1.5rem;
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: var(--bs-secondary-bg);
    transition: all 0.3s;
}

.progress-step.done .step-icon { background: var(--bs-success-bg-subtle); }
.progress-step.active .step-icon {
    background: var(--bs-warning-bg-subtle);
    animation: pulse-soft 2s infinite;
}

.progress-line {
    flex: 1;
    height: 3px;
    background: var(--bs-secondary-bg);
    min-width: 20px;
    max-width: 60px;
}

.progress-step.done ~ .progress-line,
.progress-step.done + .progress-line { background: var(--bs-success); }

.step-label { font-size: 0.75rem; margin-top: 0.25rem; color: var(--bs-secondary); }

/* Mobile: вертикальний стек */
@media (max-width: 575.98px) {
    .order-progress {
        flex-direction: column;
        align-items: flex-start;
        gap: 0;
    }
    .progress-step { flex-direction: row; gap: 0.5rem; }
    .progress-line {
        width: 3px;
        height: 20px;
        min-width: 3px;
        margin-left: 18px;
    }
    .step-label { display: inline !important; } /* Override d-none */
}
```

### 3. JS: оновлення progress bar при SSE

```javascript
// В OrderTracker.handleEvent():

case 'order_approved':
    this.updateProgress('approved');
    break;
case 'ticket_taken':
    this.updateProgress('in_progress');
    break;
case 'order_ready':
    this.updateProgress('ready');
    break;
case 'order_delivered':
    this.updateProgress('delivered');
    break;

// Метод:
updateProgress(newStatus) {
    const bar = document.querySelector('.order-progress');
    if (!bar) return;
    bar.dataset.status = newStatus;
    // Перерахувати класи done/active на кожному step
    const statusOrder = ['draft', 'submitted', 'approved', 'in_progress', 'ready', 'delivered'];
    const currentIdx = statusOrder.indexOf(newStatus);
    bar.querySelectorAll('.progress-step').forEach((step, i) => {
        step.classList.remove('done', 'active');
        if (i <= currentIdx) step.classList.add('done');
        if (i === currentIdx) step.classList.add('active');
    });
}
```

### 4. Dish-level micro-progress

Під progress bar — список страв з індивідуальним статусом (Task 9.3). Разом створюють повну картину:

```
[📝] → [👍] → [👩‍🍳 ГОТУЄТЬСЯ] → [✅] → [🍽️]
                    ↓
    🔥 Борщ — Повариха Валентина готує
    ⏳ Вареники — в черзі
    ✅ Чай — готовий
```

## Responsive

| Пристрій | Layout |
|---|---|
| Mobile (< 576px) | Вертикальний timeline, step labels видимі |
| Tablet (576-991px) | Горизонтальний, step labels видимі |
| Desktop (≥ 992px) | Горизонтальний, повна ширина |

## Тести

### Tier 2

```python
@pytest.mark.tier2
@pytest.mark.django_db
def test_progress_bar_renders_correct_classes(client, approved_order):
    """Progress bar highlights correct step for approved order."""
    response = client.get(f"/order/{order.id}/detail/?token={order.access_token}")
    content = response.content.decode()
    # approved step should have 'done' class
    assert 'data-status="approved"' in content
```

## Оцінка: 2 години

## Acceptance Criteria

- [ ] Progress bar показує 5 кроків
- [ ] Поточний крок пульсує (active)
- [ ] Минулі кроки зелені (done)
- [ ] Mobile — вертикальний, desktop — горизонтальний
- [ ] JS оновлює progress bar при SSE подіях
- [ ] SSR рендерить правильний стан без JS
- [ ] Тести зелені
