# Task 8.3 — Необов'язкова підказка місця на Order

## Мета

Дати відвідувачу можливість (не обов'язок) підказати офіціанту, де його шукати. Просте текстове поле, без зон, без структури — просто "де мене знайти".

## Контекст

Це подія діаспори. Більшість людей знайомі між собою. Ввечері темніє, починається концерт, усі переміщуються. Жорстка прив'язка до місця не працює. Але інколи людина ХОЧЕ написати "ми біля дерева" або "столик у Марини" — нехай зможе.

## Що робити

### 1. Міграція: одне поле

```python
# orders/migrations/0005_add_location_hint.py

migrations.AddField(
    model_name="order",
    name="location_hint",
    field=models.CharField(
        max_length=60,
        blank=True,
        verbose_name="Де вас знайти (необов'язково)",
    ),
)
```

### 2. Cart form — невеликий input внизу

```html
<!-- templates/orders/cart.html — перед кнопкою Submit, не акцентувати -->
<div class="mb-3">
  <input type="text"
         class="form-control form-control-sm"
         name="location_hint"
         maxlength="60"
         placeholder="{% trans 'Де вас знайти? (необов\'язково)' %}">
</div>
```

Без label, без зірочок, без zone selector — просто тихий input. Хто хоче — напише. Хто не хоче — пропустить.

### 3. Оновити submit_order_from_cart

```python
order = Order.objects.create(
    visitor=request.user if request.user.is_authenticated else None,
    location_hint=request.POST.get("location_hint", "").strip()[:60],
)
```

### 4. Відображення — тільки якщо заповнено

```html
<!-- waiter dashboard -->
{% if order.location_hint %}
  <span class="text-muted small">📍 {{ order.location_hint }}</span>
{% endif %}
```

Не badge, не alert — просто дрібний текст. Є — добре. Немає — нормально.

## Тести

```python
@pytest.mark.tier1
def test_location_hint_blank_allowed():
    """Order works fine without location_hint."""
    ...

@pytest.mark.tier2
@pytest.mark.django_db
def test_submit_saves_location_hint(client):
    """POST with location_hint saves it."""
    ...
```

## Оцінка: 0.5 години

Це мінімальна задача — одне поле, один input, мінімальне відображення.

## Acceptance Criteria

- [ ] `Order.location_hint` — CharField, max 60, blank, необов'язкове
- [ ] Cart form — простий input без акценту
- [ ] Відображається на waiter dashboard тільки якщо заповнено
- [ ] Тести зелені
