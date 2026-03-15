# Task 0.6 — SSE базова інфраструктура (детально)

## Що робимо

Налаштовуємо django-eventstream для SSE (Server-Sent Events).
Реальні події — в Sprint 4. Зараз: інфраструктура + тестовий ендпоінт.

## Чому SSE а не WebSocket

- Більшість оновлень: сервер → клієнт (нове замовлення, страва готова, ескалація)
- Клієнт надсилає дії через звичайні POST-запити
- SSE = простий HTTP, автоматичний реконнект у браузері
- Менше рухомих частин → стабільніше на слабкому мобільному 3G на фестивалі
- Django Channels + Redis потрібні для channel layers, але без складного WebSocket lifecycle

## Кроки

### 1. settings/base.py

```python
INSTALLED_APPS = [
    ...
    "channels",
    "django_eventstream",
]

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env_config("REDIS_URL", default="redis://localhost:6379/1")],
        },
    }
}
```

### 2. core_settings/asgi.py

```python
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import django_eventstream

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_settings.settings.dev")

# Важливо: get_asgi_application() викликати ДО імпорту будь-яких Django моделей
django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": URLRouter(
        django_eventstream.routing.urlpatterns
        + [
            # Всі інші HTTP запити — стандартний Django
            django_asgi_app,  # type: ignore[list-item]
        ]
    ),
})
```

### 3. core_settings/urls.py — додати SSE маршрут

```python
from django.urls import path, include
import django_eventstream

urlpatterns = [
    ...
    path("events/<str:channel>/",
         include(django_eventstream.urls),
         {"format-error": "json"}),
]
```

### 4. notifications/channels.py — визначення каналів

```python
"""
SSE channel name helpers.

Канали:
    kitchen-{user_id}  — для kitchen і kitchen_supervisor
    waiter-{user_id}   — для waiter і senior_waiter
    manager            — для manager (один глобальний канал)

Використання:
    from notifications.channels import waiter_channel
    channel = waiter_channel(request.user.id)
    send_event(channel, "message", {"type": "order_ready", "order_id": 42})
"""
from django.contrib.auth import get_user_model

User = get_user_model()


def kitchen_channel(user_id: int) -> str:
    return f"kitchen-{user_id}"


def waiter_channel(user_id: int) -> str:
    return f"waiter-{user_id}"


def manager_channel() -> str:
    return "manager"


def channels_for_user(user: User) -> list[str]:  # type: ignore[valid-type]
    """Повертає список каналів на які підписаний користувач."""
    from user.models import User as UserModel
    role = user.role
    if role in (UserModel.Role.KITCHEN, UserModel.Role.KITCHEN_SUPERVISOR):
        return [kitchen_channel(user.id)]
    if role in (UserModel.Role.WAITER, UserModel.Role.SENIOR_WAITER):
        return [waiter_channel(user.id)]
    if role == UserModel.Role.MANAGER:
        return [manager_channel()]
    return []
```

### 5. notifications/events.py — обгортка над send_event

```python
"""
Обгортка над django_eventstream.send_event.
Типізований інтерфейс для надсилання подій.
"""
from typing import Any
from django_eventstream import send_event


def push_event(channel: str, event_type: str, data: dict[str, Any]) -> None:
    """Надіслати SSE-подію у канал.

    Args:
        channel: Назва каналу (kitchen-1, waiter-2, manager).
        event_type: Тип події ('order_ready', 'escalation', тощо).
        data: Дані події — мінімальний payload для стабільності на 3G.
    """
    send_event(channel, event_type, data)
```

### 6. Перевірка вручну

```bash
# Термінал 1: запустити сервер через ASGI (uvicorn або daphne)
uv run python -m uvicorn core_settings.asgi:application --reload

# Термінал 2: підписатись на канал
curl -N http://localhost:8000/events/manager/

# Термінал 3: надіслати тестову подію
uv run python manage.py shell
>>> from notifications.events import push_event
>>> push_event("manager", "test", {"msg": "hello festival"})
```

У Терміналі 2 має зʼявитись:
```
event: test
data: {"msg": "hello festival"}
```

## Тести

```python
# tests/test_sse.py
import pytest

@pytest.mark.tier1
def test_channel_names():
    from notifications.channels import kitchen_channel, waiter_channel, manager_channel
    assert kitchen_channel(1) == "kitchen-1"
    assert waiter_channel(42) == "waiter-42"
    assert manager_channel() == "manager"

@pytest.mark.tier1
def test_channels_for_visitor_returns_empty():
    from notifications.channels import channels_for_user
    from unittest.mock import MagicMock
    from user.models import User
    user = MagicMock()
    user.role = User.Role.VISITOR
    assert channels_for_user(user) == []

@pytest.mark.tier1
def test_channels_for_kitchen():
    from notifications.channels import channels_for_user
    from unittest.mock import MagicMock
    from user.models import User
    user = MagicMock()
    user.id = 5
    user.role = User.Role.KITCHEN
    result = channels_for_user(user)
    assert result == ["kitchen-5"]

@pytest.mark.tier2
@pytest.mark.django_db
def test_sse_endpoint_exists(client):
    # SSE endpoint повертає 200 і тримає з'єднання відкритим
    # Перевіряємо тільки що ендпоінт існує (не 404)
    response = client.get("/events/manager/",
                          HTTP_ACCEPT="text/event-stream",
                          stream=True)
    assert response.status_code != 404
```

## Acceptance criteria

- [ ] `curl -N http://localhost:8000/events/manager/` — відповідає, не 404
- [ ] `push_event("manager", "test", {...})` — подія приходить у curl
- [ ] `notifications/channels.py` — 4 функції з type annotations
- [ ] `notifications/events.py` — `push_event` функція
- [ ] `uv run pytest -m tier1 tests/test_sse.py` — зелені
