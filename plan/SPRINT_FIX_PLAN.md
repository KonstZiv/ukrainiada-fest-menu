# Sprint FIX — Детальний план правок

**Мета:** закрити всі знахідки code review перед ручним тестуванням.
**Оцінка:** 4–5 годин
**Пріоритет:** 🔴 Виконати перед будь-яким тестуванням

---

## Порядок виконання

Правки мають залежності — порядок важливий:

```
FIX-1 (DRAFT→SUBMITTED)      ← блокує ВСЮ flow, робити першим
  ↓
FIX-2 (order_qr access)      ← незалежний, але швидкий
  ↓
FIX-3 (progress bar sync)    ← потребує розуміння flow після FIX-1
  ↓
FIX-5 (@require_POST)        ← незалежний, швидкий batch
  ↓
FIX-4 (reason validation)    ← незалежний
  ↓
FIX-6 (token persist)        ← потребує розуміння can_access_order
  ↓
FIX-7 ({% trans %} variable) ← незалежний
  ↓
FIX-8 (feedback double query) ← незалежний, тривіальний
  ↓
FIX-9 (total_price N+1)      ← найскладніший з бажаних, робити останнім
```

---

## 🔴 FIX-1: Відсутній перехід DRAFT → SUBMITTED

**Серйозність:** БЛОКЕР — без цього фіксу НІЧОГО не працює
**Файли:** `orders/services.py`, `orders/views.py`
**Оцінка:** 30 хв

### Проблема

`submit_order_from_cart()` створює замовлення з `status=DRAFT` (default). Коли офіціант натискає "Підтвердити", `approve_order()` перевіряє `if order.status != SUBMITTED: raise ValueError`. Перехід DRAFT→SUBMITTED ніде не відбувається.

### Аналіз бізнес-логіки

Згідно PROJECT.md pipeline:
```
visitor: draft → (показує QR офіціанту) → submitted → approved
```

Є два варіанти дизайну, і треба обрати один:

**Варіант A — "Submit = уже SUBMITTED"** (рекомендований):
Коли відвідувач натискає "Оформити замовлення", воно одразу стає SUBMITTED. DRAFT існує тільки поки замовлення у кошику (як концепт).

Це простіше, менше кроків, відвідувачу не треба робити додатковий "підтвердити".

**Варіант B — "Submit = DRAFT, потрібен явний крок SUBMITTED"**:
Замовлення створюється як DRAFT, відвідувач бачить QR, і тільки коли офіціант сканує QR — замовлення стає SUBMITTED. Це дає відвідувачу можливість скасувати.

Складніше, потребує додатковий view/сервіс.

### План (Варіант A — рекомендований)

**`orders/services.py`** — `submit_order_from_cart()`:

```python
# Замінити:
order = Order.objects.create(
    visitor=request.user if request.user.is_authenticated else None,
    location_hint=location_hint,
)

# На:
order = Order.objects.create(
    visitor=request.user if request.user.is_authenticated else None,
    location_hint=location_hint,
    status=Order.Status.SUBMITTED,
    submitted_at=timezone.now(),
)
```

**`orders/views.py`** — `order_qr()`:

```python
# Замінити:
order = get_object_or_404(Order, pk=order_id, status=Order.Status.DRAFT)

# На:
order = get_object_or_404(Order, pk=order_id, status=Order.Status.SUBMITTED)
```

**`templates/orders/order_detail.html`** — умови для QR-коду:

```html
<!-- Замінити всі перевірки 'draft' на 'submitted' де стосується QR -->
{% if order.status == 'submitted' %}
    <!-- QR block -->
{% endif %}
```

Шаблон має 4 місця з перевіркою `draft`:
- Рядок 11: `{% if order.status != 'draft' %}` — progress bar → НЕ МІНЯТИ (progress bar не потрібен для submitted, це ОК)
- Рядок 32: `{% if ticket_states and order.status != 'draft' %}` → замінити на `!= 'submitted'` (тікетів немає до approve)
- Рядок 156: `{# Simple item list for draft orders #}` → це else гілка, стосується submitted
- Рядок 172: `{% if order.status == 'draft' %}` — QR блок → замінити на `== 'submitted'`
- Рядок 186: `{% if order.status != 'draft' and order.status != 'delivered' %}` — JS tracker → `!= 'submitted'`

**Увага:** ретельно пройтись по всіх `draft` у шаблонах і views. Grep: `grep -rn "draft\|DRAFT" templates/ orders/`.

**`orders/views.py`** — docstring `submit_order_from_cart`:

```python
# Замінити:
"""Create a DRAFT Order from session cart contents."""
# На:
"""Create a SUBMITTED Order from session cart contents."""
```

### Тести для перевірки

```python
@pytest.mark.django_db
def test_submit_creates_submitted_order(rf):
    """submit_order_from_cart creates order with SUBMITTED status."""
    # setup cart, call submit
    assert order.status == Order.Status.SUBMITTED
    assert order.submitted_at is not None

@pytest.mark.django_db
def test_approve_works_after_submit(rf, django_user_model):
    """Full flow: submit → approve succeeds."""
    # create order via submit, then approve
    approved = approve_order(order, waiter)
    assert approved.status == Order.Status.APPROVED
```

---

## 🔴 FIX-2: `order_qr` без контролю доступу

**Серйозність:** БЕЗПЕКА
**Файл:** `orders/views.py`
**Оцінка:** 5 хв

### Проблема

```python
def order_qr(request, order_id):
    order = get_object_or_404(Order, pk=order_id, status=Order.Status.DRAFT)
    # ← can_access_order не викликається
```

### План

```python
def order_qr(request: HttpRequest, order_id: int) -> HttpResponse:
    order = get_object_or_404(Order, pk=order_id, status=Order.Status.SUBMITTED)  # FIX-1
    if not can_access_order(request, order):
        return HttpResponse(status=403)
    # ... решта без змін
```

### Тест

```python
@pytest.mark.django_db
def test_order_qr_denied_for_stranger(client):
    order = Order.objects.create(status=Order.Status.SUBMITTED)
    response = client.get(f"/order/{order.id}/qr/")
    assert response.status_code == 403
```

---

## 🔴 FIX-3: Progress bar JS/SSR розсинхронізація

**Серйозність:** ВІЗУАЛЬНИЙ БАГ — progress bar "стрибає"
**Файли:** `orders/views.py`, `staticfiles/js/order_tracker.js`
**Оцінка:** 30 хв

### Проблема

Сервер має 6 статусів замовлення, але тільки 5 кроків на progress bar. Mapping між ними різний на сервері і в JS.

**Сервер (`_build_progress_steps`):** використовує `thresholds = [0, 2, 3, 4, 5]` — пропускає index 1 (submitted).

**JS (`updateProgress`):** використовує `STATUS_ORDER.indexOf()` напряму — 6 значень маплять на 5 DOM-елементів, тобто при `STATUS_ORDER.indexOf("submitted") = 1` крок steps[1] отримує `active`, хоча це вже "Прийнято".

### Суть проблеми

Progress bar показує 5 візуальних кроків:
```
[0] Створено  [1] Прийнято  [2] Готується  [3] Готово  [4] Доставлено
```

А статусів 6:
```
draft(0)  submitted(1)  approved(2)  in_progress(3)  ready(4)  delivered(5)
```

Mapping: submitted і approved обидва відповідають кроку [1] "Прийнято". Решта — 1:1.

### План — уніфікувати через єдиний mapping

**`orders/views.py`** — спростити `_build_progress_steps`:

```python
def _build_progress_steps(order_status: str) -> list[dict[str, object]]:
    from django.utils.translation import gettext as _

    # Mapping: 6 order statuses → 5 visual steps (0-indexed)
    # submitted and approved both map to step 1 ("Прийнято")
    STATUS_TO_STEP: dict[str, int] = {
        "draft": -1,           # no step active
        "submitted": 0,        # step 0: Створено (waiting for waiter)
        "approved": 1,         # step 1: Прийнято
        "in_progress": 2,      # step 2: Готується
        "ready": 3,            # step 3: Готово
        "delivered": 4,        # step 4: Доставлено
    }

    current_step = STATUS_TO_STEP.get(order_status, -1)

    steps_config = [
        ("📝", _("Створено")),
        ("👍", _("Прийнято")),
        ("👩‍🍳", _("Готується")),
        ("✅", _("Готово")),
        ("🍽️", _("Доставлено")),
    ]

    return [
        {
            "icon": icon,
            "label": label,
            "done": i <= current_step,
            "active": i == current_step,
            "step_index": i,
        }
        for i, (icon, label) in enumerate(steps_config)
    ]
```

**Шаблон** — додати `data-step-index` на кожен step:

```html
<div class="progress-step {% if step.done %}done{% endif %} {% if step.active %}active{% endif %}"
     data-step-index="{{ step.step_index }}">
```

**`staticfiles/js/order_tracker.js`** — використовувати той самий mapping:

```javascript
const STATUS_TO_STEP = {
    "draft": -1,
    "submitted": 0,
    "approved": 1,
    "in_progress": 2,
    "ready": 3,
    "delivered": 4,
};

updateProgress(newStatus) {
    const bar = document.querySelector(".order-progress");
    if (!bar) return;
    const targetStep = STATUS_TO_STEP[newStatus];
    if (targetStep === undefined) return;

    bar.querySelectorAll(".progress-step").forEach((step) => {
        const idx = parseInt(step.dataset.stepIndex, 10);
        step.classList.remove("done", "active");
        if (idx <= targetStep) step.classList.add("done");
        if (idx === targetStep) step.classList.add("active");
    });
}
```

### Тест

```python
@pytest.mark.tier1
def test_progress_steps_submitted():
    steps = _build_progress_steps("submitted")
    assert steps[0]["done"] is True   # Створено
    assert steps[0]["active"] is True
    assert steps[1]["done"] is False  # Прийнято — ще ні

@pytest.mark.tier1
def test_progress_steps_approved():
    steps = _build_progress_steps("approved")
    assert steps[0]["done"] is True
    assert steps[1]["done"] is True   # Прийнято
    assert steps[1]["active"] is True
    assert steps[2]["done"] is False  # Готується — ще ні

@pytest.mark.tier1
def test_progress_steps_labels_are_translated():
    """Labels should be strings, not lazy proxies that break in template."""
    steps = _build_progress_steps("draft")
    assert isinstance(steps[0]["label"], str)
```

---

## 🔴 FIX-4: `create_escalation` не валідує `reason`

**Серйозність:** ПОРУШЕННЯ АРХІТЕКТУРИ — бізнес-логіка має бути в сервісі
**Файл:** `orders/escalation_services.py`
**Оцінка:** 5 хв

### План

Додати валідацію на початку `create_escalation()`, прибрати з view:

```python
# orders/escalation_services.py — create_escalation(), на початку:

if reason not in VisitorEscalation.Reason.values:
    msg = f"Невідома причина звернення: {reason}"
    raise ValueError(msg)
```

```python
# orders/views.py — create_escalation_view():
# Видалити ці рядки (валідація тепер у сервісі):
if reason not in VisitorEscalation.Reason.values:
    messages.warning(request, "Будь ласка, оберіть дійсну причину звернення.")
    return redirect("orders:order_detail", order_id=order_id)

# Залишити тільки:
try:
    create_escalation(order, reason=reason, message=message)
    messages.success(request, "Ваше звернення надіслано!")
except ValueError as e:
    messages.warning(request, str(e))
```

### Тест

```python
@pytest.mark.django_db
def test_create_escalation_invalid_reason():
    order = Order.objects.create(
        status=Order.Status.APPROVED,
        approved_at=timezone.now() - timedelta(minutes=10),
    )
    with pytest.raises(ValueError, match="Невідома причина"):
        create_escalation(order, reason="nonexistent")
```

---

## 🔴 FIX-5: `@require_POST` консистентність

**Серйозність:** INCONSISTENCY + потенційна проблема (GET-запити змінюють стан)
**Файли:** `orders/views.py`, `orders/waiter_views.py`
**Оцінка:** 10 хв

### Проблема

Деякі POST-only views перевіряють `if request.method == "POST"` вручну замість `@require_POST`. Це inconsistent з рештою проєкту і дозволяє GET-запити (які нічого не роблять, але створюють зайвий redirect).

### План — додати `@require_POST` до:

**`orders/views.py`:**

```python
@require_POST                          # ДОДАТИ
def cart_add(request, ...):
    # Видалити: if request.method == "POST":
    try:
        ...
    except ValueError, TypeError:
        return redirect("orders:cart")
    ...

@require_POST                          # ДОДАТИ
def order_submit(request, ...):
    # Видалити: if request.method == "POST":
    order = submit_order_from_cart(request)
    ...
```

**`orders/waiter_views.py`:**

```python
@role_required(*WAITER_ROLES)
@require_POST                          # ДОДАТИ
def order_approve(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    # Видалити: if request.method == "POST":
    try:
        approve_order(order, request.user)
        ...

@role_required(*WAITER_ROLES)
@require_POST                          # ДОДАТИ
def order_mark_delivered(request, order_id):
    # Видалити: if request.method != "POST": return redirect(...)
    order = get_object_or_404(...)
    ...

@role_required(*WAITER_ROLES)
@require_POST                          # ДОДАТИ
def order_confirm_payment(request, order_id):
    # Видалити: if request.method != "POST": return redirect(...)
    ...
```

**Важливо:** `require_POST` повертає `HttpResponseNotAllowed(["POST"])` (405) замість тихого redirect. Це правильна поведінка.

### Перевірка

`grep -rn "request.method" orders/views.py orders/waiter_views.py` — після фіксу не повинно бути жодного `request.method == "POST"` перевірки (крім `handoff_confirm_view`, який легітимно має GET + POST).

---

## 🟡 FIX-6: Token не зберігається в session при GET через `?token=`

**Серйозність:** ФУНКЦІОНАЛЬНИЙ БАГ для shared URLs
**Файли:** `orders/views.py` або `orders/services.py`
**Оцінка:** 15 хв

### Проблема

Сценарій:
1. Відвідувач А створює замовлення → token у session
2. А ділиться URL `/order/5/?token=abc123` з відвідувачем Б
3. Б відкриває URL → `can_access_order` перевіряє `?token=` → OK, бачить замовлення
4. Б натискає "Надіслати відгук" → POST на `/feedback/5/submit/` (без `?token=`)
5. `can_access_order` перевіряє session → token НЕ збережений → 403

Та сама проблема для ескалації та онлайн-оплати.

### План

**Варіант A (рекомендований) — persist token при успішному GET-доступі:**

```python
# orders/views.py — order_detail(), ПІСЛЯ перевірки can_access_order:

def order_detail(request, order_id):
    order = get_object_or_404(...)
    if not can_access_order(request, order):
        return render(request, "403.html", status=403)

    # Persist token in session if accessed via ?token= (for subsequent POSTs)
    url_token = request.GET.get("token", "")
    if url_token and str(order.access_token) == url_token:
        if "my_orders" not in request.session:
            request.session["my_orders"] = {}
        request.session["my_orders"][str(order.id)] = str(order.access_token)
        request.session.modified = True

    # ... решта view
```

Це елегантно: якщо людина бачить сторінку через `?token=`, всі наступні POST-запити (feedback, escalation) теж будуть авторизовані через session.

**Варіант B — додати hidden input з token у кожну форму:**

Більше змін у шаблонах, менш надійно (треба в кожну форму додавати).

### Тест

```python
@pytest.mark.django_db
def test_token_persisted_in_session_on_get(client):
    """Accessing order_detail via ?token= saves token to session."""
    order = Order.objects.create(status=Order.Status.DELIVERED)
    # Access via token
    client.get(f"/order/{order.id}/?token={order.access_token}")
    # Now POST without token should work
    response = client.post(f"/feedback/{order.id}/submit/", {"mood": "love"})
    assert response.status_code == 302  # redirect, not 403
```

---

## 🟡 FIX-7: `{% trans step.label %}` не працює зі змінною

**Серйозність:** i18n НЕ ПРАЦЮЄ для progress bar labels
**Файли:** `orders/views.py`, `templates/orders/order_detail.html`
**Оцінка:** 10 хв

### Проблема

```html
<span class="step-label">{% trans step.label %}</span>
```

`{% trans %}` tag працює **тільки** зі строковими літералами: `{% trans "Hello" %}`. Для змінних Django поверне рядок як є, без перекладу.

### План

Вже виправлено в FIX-3: `_build_progress_steps` тепер використовує `gettext()` при створенні labels, тому в шаблоні просто:

```html
<!-- Замінити: -->
<span class="step-label d-none d-sm-inline">{% trans step.label %}</span>

<!-- На: -->
<span class="step-label d-none d-sm-inline">{{ step.label }}</span>
```

Labels вже перекладені на рівні Python через `_("Створено")` і т.д.

---

## 🟡 FIX-8: Подвійний запит для feedback в order_detail

**Серйозність:** ПЕРФОРМАНС (мінорний)
**Файл:** `orders/views.py`
**Оцінка:** 5 хв

### Проблема

```python
has_feedback = GuestFeedback.objects.filter(order=order).exists()  # SQL 1
if has_feedback:
    feedback_obj = order.feedback  # SQL 2 (lazy load через OneToOne)
```

### План

```python
# Замінити на:
feedback_obj = GuestFeedback.objects.filter(order=order).first()
has_feedback = feedback_obj is not None
```

Один запит замість двох. `first()` повертає об'єкт або None.

---

## 🟡 FIX-9: `total_price` property — N+1 запитів

**Серйозність:** ПЕРФОРМАНС — помітно при 20+ замовлень на dashboard
**Файли:** `orders/models.py`, `orders/waiter_views.py`, `templates/`
**Оцінка:** 30 хв

### Проблема

Кожен виклик `order.total_price` у шаблоні = окремий SQL `aggregate()`. На waiter dashboard з 20 замовленнями — 20 зайвих запитів.

### План — annotate в QuerySet

**`orders/waiter_views.py`** — `waiter_dashboard()`:

```python
from django.db.models import F, Sum, DecimalField

orders = (
    Order.objects.filter(waiter=request.user, status__in=active_statuses)
    .prefetch_related(...)
    .annotate(
        total_annotated=Sum(
            F("items__dish__price") * F("items__quantity"),
            output_field=DecimalField(),
        )
    )
    .order_by("created_at")
)
```

**`templates/orders/waiter_dashboard.html`:**

```html
<!-- Замінити: -->
{{ order.total_price|floatformat:2 }}

<!-- На: -->
{{ order.total_annotated|floatformat:2 }}
```

**`orders/models.py`** — залишити `total_price` property як є (для backward compatibility і одиночних об'єктів). Додати коментар:

```python
@property
def total_price(self) -> Decimal:
    """Calculate total price using DB aggregation.

    NOTE: For list views, prefer annotate(total_annotated=...) on QuerySet
    to avoid N+1 queries. This property is for single-object access.
    """
```

Аналогічно annotate для:
- `waiter_order_list` (якщо показує ціни)
- `senior_waiter_dashboard` (якщо показує ціни)

**`order_detail.html`** — тут залишити `total_price` (один об'єкт, один запит — прийнятно).

### Тест

```python
@pytest.mark.django_db
def test_waiter_dashboard_query_count(waiter_client, django_assert_num_queries):
    """Dashboard with 10 orders should not exceed N queries."""
    # Create 10 orders with items
    with django_assert_num_queries(10):  # adjust threshold
        response = waiter_client.get("/waiter/dashboard/")
    assert response.status_code == 200
```

---

## Зведена таблиця

| # | Назва | Серйозність | Файли | Оцінка |
|---|---|---|---|---|
| FIX-1 | DRAFT→SUBMITTED | 🔴 БЛОКЕР | services, views, template | 30 хв |
| FIX-2 | order_qr access | 🔴 Безпека | views.py | 5 хв |
| FIX-3 | Progress bar sync | 🔴 Візуальний | views.py, JS, template | 30 хв |
| FIX-4 | Reason validation | 🔴 Архітектура | escalation_services.py | 5 хв |
| FIX-5 | @require_POST | 🔴 Консистентність | views.py, waiter_views.py | 10 хв |
| FIX-6 | Token persist | 🟡 Функціональний | views.py | 15 хв |
| FIX-7 | {% trans %} variable | 🟡 i18n | template | 10 хв |
| FIX-8 | Feedback double query | 🟡 Перформанс | views.py | 5 хв |
| FIX-9 | total_price N+1 | 🟡 Перформанс | models, views, templates | 30 хв |
| | | | **Разом:** | **~2.5 год** |

---

## Після всіх правок — перевірки

```bash
# 1. Лінтер
uv run ruff check . && uv run ruff format --check .

# 2. Типи
uv run mypy .

# 3. Тести
uv run pytest -m "tier1 or tier2" -v

# 4. Grep-перевірки
grep -rn "request.method.*POST" orders/    # Має бути тільки в handoff_confirm_view
grep -rn "\.DRAFT" orders/                 # Має бути тільки в моделі (TextChoices)
grep -rn "trans step\." templates/         # Не повинно бути жодного
```
