# Task 0.4 — Бізнес-константи в settings (детально)

## Що робимо

Всі фестивальні таймаути — в `settings/base.py`, керуються через `.env`.
Принцип: перед фестивалем організатор може змінити таймаути без правки коду.

## settings/base.py — додати блок

```python
# ---------------------------------------------------------------------------
# Festival service configuration
# Всі значення в хвилинах якщо не вказано інше.
# Змінюються через .env перед кожним фестивалем.
# ---------------------------------------------------------------------------

# Час після якого нічийне замовлення зʼявляється у kitchen_supervisor
KITCHEN_TIMEOUT: int = env_config("KITCHEN_TIMEOUT", default=5, cast=int)

# Додатковий час після KITCHEN_TIMEOUT до ескалації на manager
MANAGER_TIMEOUT: int = env_config("MANAGER_TIMEOUT", default=5, cast=int)

# Час після передачі страви офіціанту до ескалації несплаченого замовлення
PAY_TIMEOUT: int = env_config("PAY_TIMEOUT", default=10, cast=int)

# Вікно часу для підрахунку throughput кухні (скільки страв видано за N хвилин)
SPEED_INTERVAL_KITCHEN: int = env_config("SPEED_INTERVAL_KITCHEN", default=15, cast=int)
```

## Утилітарна функція для використання в коді

```python
# core_settings/timeouts.py
from django.conf import settings
from datetime import timedelta


def kitchen_timeout() -> timedelta:
    return timedelta(minutes=settings.KITCHEN_TIMEOUT)


def manager_timeout() -> timedelta:
    """Повний таймаут до менеджера = KITCHEN_TIMEOUT + MANAGER_TIMEOUT."""
    return timedelta(minutes=settings.KITCHEN_TIMEOUT + settings.MANAGER_TIMEOUT)


def pay_timeout() -> timedelta:
    return timedelta(minutes=settings.PAY_TIMEOUT)
```

## Тести

```python
# tests/test_timeouts.py
import pytest
from datetime import timedelta

@pytest.mark.tier1
def test_kitchen_timeout_default():
    from core_settings.timeouts import kitchen_timeout
    assert kitchen_timeout() == timedelta(minutes=5)

@pytest.mark.tier1
def test_manager_timeout_is_cumulative():
    from core_settings.timeouts import manager_timeout
    # manager_timeout = KITCHEN_TIMEOUT + MANAGER_TIMEOUT = 5 + 5 = 10
    assert manager_timeout() == timedelta(minutes=10)

@pytest.mark.tier1
def test_pay_timeout_default():
    from core_settings.timeouts import pay_timeout
    assert pay_timeout() == timedelta(minutes=10)

@pytest.mark.tier1
def test_settings_are_integers():
    from django.conf import settings
    assert isinstance(settings.KITCHEN_TIMEOUT, int)
    assert isinstance(settings.MANAGER_TIMEOUT, int)
    assert isinstance(settings.PAY_TIMEOUT, int)
    assert isinstance(settings.SPEED_INTERVAL_KITCHEN, int)
```

## Acceptance criteria

- [ ] Всі 4 константи читаються з `.env` через `decouple.config`
- [ ] `core_settings/timeouts.py` існує з трьома функціями
- [ ] `uv run pytest -m tier1 tests/test_timeouts.py` — зелені
