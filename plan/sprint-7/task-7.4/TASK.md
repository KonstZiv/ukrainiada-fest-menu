# Task 7.4 — Офлайн-сторінка з кешованим меню (детально)

## Концепція

Service Worker (Task 7.3) вже кешує `/order/menu/` при першому відвідуванні.
Цей таск — допрацювати UX офлайн-режиму:

1. Банер "Ви в офлайн-режимі — меню може бути застарілим"
2. Кошик — заблокований (не можна оформити замовлення без інтернету)
3. Форми — відключені з поясненням
4. Коли зʼявляється мережа — автоматичне сповіщення

## staticfiles/js/offline_detector.js

```javascript
/**
 * Детектор офлайн-режиму.
 * Показує/ховає банер і блокує форми.
 */
(function () {
    'use strict';

    const OFFLINE_BANNER_ID = 'offline-banner';
    const BLOCKED_FORMS_CLASS = 'form-needs-network';

    function showOfflineBanner() {
        let banner = document.getElementById(OFFLINE_BANNER_ID);
        if (!banner) {
            banner = document.createElement('div');
            banner.id = OFFLINE_BANNER_ID;
            banner.innerHTML = `
                <div style="background:#856404; color:#fff3cd; padding:10px 16px;
                            text-align:center; font-size:0.9rem; position:sticky;
                            top:0; z-index:999;">
                    📵 Офлайн-режим — меню може бути застарілим.
                    Замовлення недоступні без інтернету.
                </div>
            `;
            document.body.prepend(banner);
        }

        // Блокуємо форми що потребують мережі
        document.querySelectorAll('.' + BLOCKED_FORMS_CLASS).forEach((form) => {
            form.querySelectorAll('button[type="submit"], input[type="submit"]')
                .forEach((btn) => {
                    btn.disabled = true;
                    btn.title = 'Недоступно в офлайн-режимі';
                });
        });
    }

    function hideOfflineBanner() {
        const banner = document.getElementById(OFFLINE_BANNER_ID);
        if (banner) {
            banner.remove();
        }

        // Розблоковуємо форми
        document.querySelectorAll('.' + BLOCKED_FORMS_CLASS).forEach((form) => {
            form.querySelectorAll('button[type="submit"], input[type="submit"]')
                .forEach((btn) => {
                    btn.disabled = false;
                });
        });
    }

    function onOnline() {
        hideOfflineBanner();
        // Сповіщення що звʼязок відновлено
        if (window.showFlash) {
            window.showFlash('✅ Звʼязок відновлено!', 'success');
        } else {
            console.log('[Network] Back online');
        }
    }

    function onOffline() {
        showOfflineBanner();
    }

    // Початковий стан
    if (!navigator.onLine) {
        document.addEventListener('DOMContentLoaded', showOfflineBanner);
    }

    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);
})();
```

## Підключення в base шаблонах

```html
<!-- base_visitor.html і base_staff.html — додати після visitor.css / staff.css -->
{% load static %}
<script src="{% static 'js/offline_detector.js' %}" defer></script>
```

## Позначення форм що потребують мережі

```html
<!-- orders/cart.html — форма оформлення замовлення -->
<form method="post" action="{% url 'orders:order_submit' %}"
      class="form-needs-network">
    {% csrf_token %}
    <button type="submit" class="btn btn-primary btn-lg w-100">
        📋 Оформити замовлення
    </button>
</form>

<!-- Пояснення для відвідувача -->
<p class="text-muted text-center mt-2 offline-only" style="display:none">
    <small>Для оформлення замовлення потрібен інтернет</small>
</p>
```

## Django view — меню з cache-hint headers

```python
# orders/views.py — visitor_menu — додати cache headers

from django.views.decorators.cache import cache_control


@cache_control(public=True, max_age=300)  # 5 хвилин кеш для браузера
def visitor_menu(request: HttpRequest) -> HttpResponse:
    """Меню для відвідувача.

    cache-control: public, max-age=300 — браузер і Service Worker
    кешують сторінку до 5 хвилин, після чого перевіряють оновлення.
    """
    categories = (
        Category.objects.select_related("logo")
        .prefetch_related(
            "dishes__allergens",
            "dishes__main_image",
        )
        .exclude(dishes__availability="out")
    )
    return render(request, "orders/visitor_menu.html", {"categories": categories})
```

## Оновлення sw.js — versioned cache + background sync

```javascript
// Додати до sw.js — перевірка версії кешу меню
const MENU_CACHE_NAME = 'festival-menu-pages-v1';
const MENU_URL = '/order/menu/';

// Background sync — оновлення меню коли зʼявляється мережа
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-menu') {
        event.waitUntil(
            fetch(MENU_URL)
                .then((response) => {
                    if (response.ok) {
                        return caches.open(MENU_CACHE_NAME).then((cache) => {
                            return cache.put(MENU_URL, response);
                        });
                    }
                })
                .catch(() => {
                    console.log('[SW] Background sync failed, will retry');
                })
        );
    }
});
```

## Тести

```python
# tests/test_offline.py
import pytest


@pytest.mark.tier1
def test_offline_detector_js_exists():
    import os
    assert os.path.exists(os.path.join("staticfiles", "js", "offline_detector.js"))


@pytest.mark.tier2
@pytest.mark.django_db
def test_visitor_menu_has_cache_headers(client):
    response = client.get("/order/menu/")
    assert response.status_code == 200
    cache_control = response.get("Cache-Control", "")
    # cache-control header встановлений
    assert "max-age" in cache_control or "public" in cache_control


@pytest.mark.tier2
@pytest.mark.django_db
def test_visitor_menu_cacheable_by_service_worker(client):
    """Меню повертає 200 і правильний content-type для кешування SW."""
    response = client.get("/order/menu/")
    assert response.status_code == 200
    assert "text/html" in response.get("Content-Type", "")


@pytest.mark.tier3
def test_menu_available_offline():
    """
    E2E тест: Service Worker кешує меню, відключаємо мережу,
    перевіряємо що меню все ще доступне.

    Потребує Playwright або Selenium з network throttling.
    Запускається тільки перед деплоєм (tier3).
    """
    # TODO: реалізувати в рамках E2E suite
    pass
```

## Lighthouse перевірка

```bash
# Запустити після деплою або в dev з HTTPS
npx lighthouse https://localhost:8000/order/menu/ \
  --only-categories=pwa \
  --output=json \
  --output-path=./lighthouse-pwa.json

# Мінімальний score: 80
```

## Acceptance criteria

- [ ] Офлайн банер зʼявляється автоматично при втраті мережі
- [ ] Форма "Оформити замовлення" — заблокована офлайн
- [ ] При відновленні мережі — банер зникає, форми розблоковуються
- [ ] `/order/menu/` — `Cache-Control: public, max-age=300`
- [ ] Service Worker кешує меню при першому відвідуванні
- [ ] Lighthouse PWA score ≥ 80 (tier3 перевірка)
- [ ] `uv run pytest -m "tier1 or tier2"` — зелені
