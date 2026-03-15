# Task 4.1 — SSE view і підписка клієнта (детально)

## notifications/views.py

```python
from django.http import HttpRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django_eventstream import EventResponse
from notifications.channels import channels_for_user


@login_required
def user_events(request: HttpRequest) -> HttpResponse:
    """SSE endpoint — повертає потік подій для поточного користувача.

    Клієнт підключається до /events/stream/ і отримує всі події
    для своїх каналів (залежить від ролі).

    Повертає 403 якщо користувач не має каналів (наприклад, visitor).
    """
    channels = channels_for_user(request.user)
    if not channels:
        return HttpResponse("No channels for your role", status=403)

    return EventResponse(channels)
```

## notifications/urls.py

```python
from django.urls import path
from notifications import views

app_name = "notifications"

urlpatterns = [
    path("stream/", views.user_events, name="user_events"),
]
```

## core_settings/urls.py — додати

```python
path("events/", include("notifications.urls")),
```

## JS клієнт — base template

```html
<!-- templates/base_staff.html — базовий шаблон для kitchen/waiter/manager -->
{% if user.is_authenticated %}
<script>
(function() {
    const source = new EventSource("{% url 'notifications:user_events' %}");

    source.onopen = function() {
        console.log('[SSE] Connected');
    };

    source.onerror = function(e) {
        console.warn('[SSE] Connection error, will retry...', e);
        // EventSource автоматично перепідключається — нічого додаткового не треба
    };

    // Загальний обробник — делегує специфічним handlers
    source.addEventListener('message', function(e) {
        try {
            const data = JSON.parse(e.data);
            window.dispatchEvent(new CustomEvent('sse:' + data.type, { detail: data }));
        } catch(err) {
            console.error('[SSE] Parse error', err);
        }
    });

    // Обробники специфічних подій — підключаються на конкретних сторінках
    // Дивись Task 4.3
})();
</script>
{% endif %}
```

## Тести

```python
# notifications/tests/test_sse_view.py
import pytest


@pytest.mark.tier2
@pytest.mark.django_db
def test_sse_requires_auth(client):
    response = client.get("/events/stream/")
    assert response.status_code == 302  # redirect to login


@pytest.mark.tier2
@pytest.mark.django_db
def test_visitor_gets_403(client, django_user_model):
    visitor = django_user_model.objects.create_user(
        email="v@test.com", password="pass", role="visitor"
    )
    client.force_login(visitor)
    response = client.get("/events/stream/")
    assert response.status_code == 403


@pytest.mark.tier2
@pytest.mark.django_db
def test_kitchen_user_gets_stream(client, django_user_model):
    kitchen = django_user_model.objects.create_user(
        email="k@test.com", password="pass", role="kitchen"
    )
    client.force_login(kitchen)
    response = client.get("/events/stream/",
                          HTTP_ACCEPT="text/event-stream")
    assert response.status_code == 200


@pytest.mark.tier1
def test_channels_for_user_kitchen():
    from notifications.channels import channels_for_user
    from unittest.mock import MagicMock
    from user.models import User
    user = MagicMock()
    user.id = 7
    user.role = User.Role.KITCHEN
    assert channels_for_user(user) == ["kitchen-7"]
```

## Acceptance criteria

- [ ] `/events/stream/` — 302 для анонімних, 403 для visitor, 200 для staff
- [ ] Кожна роль отримує правильний набір каналів
- [ ] JS підключається і логує `[SSE] Connected`
- [ ] Тести зелені
