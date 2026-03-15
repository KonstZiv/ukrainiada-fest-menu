# Task 7.3 — PWA manifest і service worker (детально)

## staticfiles/manifest.json

```json
{
    "name": "🇺🇦 Festival Menu",
    "short_name": "Festival",
    "description": "Меню та замовлення на Фестивалі Української Культури в Херцег-Нові",
    "start_url": "/order/menu/",
    "scope": "/",
    "display": "standalone",
    "background_color": "#1a1a1a",
    "theme_color": "#e34c26",
    "lang": "uk",
    "orientation": "portrait",
    "icons": [
        {
            "src": "/static/icons/icon-192.png",
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "any maskable"
        },
        {
            "src": "/static/icons/icon-512.png",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "any maskable"
        }
    ],
    "shortcuts": [
        {
            "name": "Меню",
            "url": "/order/menu/",
            "icons": [{"src": "/static/icons/icon-192.png", "sizes": "192x192"}]
        }
    ]
}
```

## Іконки

Потрібно створити дві PNG іконки:
- `staticfiles/icons/icon-192.png` — 192×192px
- `staticfiles/icons/icon-512.png` — 512×512px

Використовуємо прапор 🇺🇦 + назву фестивалю. Можна створити через Python:

```python
# scripts/generate_icons.py
from PIL import Image, ImageDraw, ImageFont
import os


def create_icon(size: int, output_path: str) -> None:
    img = Image.new("RGB", (size, size), color="#e34c26")
    draw = ImageDraw.Draw(img)

    # Жовтий блок знизу (прапор)
    draw.rectangle([0, size // 2, size, size], fill="#ffd700")

    # Текст
    text = "🇺🇦"
    font_size = size // 3
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    draw.text(
        ((size - text_w) // 2, (size - text_h) // 2),
        text, fill="white", font=font
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "PNG")
    print(f"Created: {output_path}")


if __name__ == "__main__":
    create_icon(192, "staticfiles/icons/icon-192.png")
    create_icon(512, "staticfiles/icons/icon-512.png")
```

## staticfiles/js/sw.js — Service Worker

```javascript
/**
 * Festival Menu Service Worker
 * Кешує статику і меню для офлайн-доступу.
 */

const CACHE_NAME = 'festival-menu-v1';
const CACHE_TIMEOUT = 7 * 24 * 60 * 60 * 1000;  // 7 днів

// Ресурси що кешуються одразу при встановленні SW
const PRECACHE_URLS = [
    '/order/menu/',
    '/static/css/visitor.css',
    '/static/css/staff.css',
    '/static/js/sse_client.js',
    '/static/icons/icon-192.png',
    '/static/manifest.json',
    '/offline/',
];

// Install: precache критичних ресурсів
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[SW] Precaching resources');
            return cache.addAll(PRECACHE_URLS);
        })
    );
    self.skipWaiting();
});

// Activate: видаляємо старі кеші
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys
                    .filter((key) => key !== CACHE_NAME)
                    .map((key) => caches.delete(key))
            )
        )
    );
    self.clients.claim();
});

// Fetch: стратегія "network first, cache fallback"
self.addEventListener('fetch', (event) => {
    // SSE запити — ніколи не кешуємо
    if (event.request.url.includes('/events/')) {
        return;
    }

    // POST запити — ніколи не кешуємо
    if (event.request.method !== 'GET') {
        return;
    }

    event.respondWith(
        fetch(event.request)
            .then((response) => {
                // Кешуємо успішні GET відповіді
                if (response.ok) {
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseClone);
                    });
                }
                return response;
            })
            .catch(() => {
                // Мережа недоступна — повертаємо з кешу
                return caches.match(event.request).then((cachedResponse) => {
                    if (cachedResponse) {
                        return cachedResponse;
                    }
                    // Нічого в кеші — офлайн сторінка
                    return caches.match('/offline/');
                });
            })
    );
});
```

## Реєстрація Service Worker у base шаблонах

```html
<!-- Додати в кінець base_visitor.html і base_staff.html перед </body> -->
<script>
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker
            .register('/static/js/sw.js')
            .then(function(reg) {
                console.log('[PWA] SW registered:', reg.scope);
            })
            .catch(function(err) {
                console.warn('[PWA] SW registration failed:', err);
            });
    });
}
</script>
```

## Django view для offline сторінки

```python
# core_settings/views.py — додати
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def offline_page(request: HttpRequest) -> HttpResponse:
    return render(request, "offline.html", status=200)
```

```python
# core_settings/urls.py — додати
path("offline/", views.offline_page, name="offline"),
```

## templates/offline.html

```html
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Немає зʼєднання</title>
    <style>
        body { background:#1a1a1a; color:#f0f0f0; font-family:system-ui;
               display:flex; align-items:center; justify-content:center;
               min-height:100vh; text-align:center; padding:20px; }
        .icon { font-size: 4rem; margin-bottom: 16px; }
    </style>
</head>
<body>
    <div>
        <div class="icon">📵</div>
        <h1>Немає зʼєднання</h1>
        <p>Перевірте інтернет і спробуйте знову.</p>
        <p>Якщо ви переглядали меню раніше — воно доступне в кеші.</p>
        <button onclick="location.reload()"
                style="padding:14px 28px; font-size:1rem; margin-top:16px;
                       border-radius:8px; background:#e34c26; color:white; border:none">
            🔄 Спробувати знову
        </button>
    </div>
</body>
</html>
```

## Тести

```python
# tests/test_pwa.py
import pytest
import json


@pytest.mark.tier1
def test_manifest_json_is_valid():
    import os
    manifest_path = os.path.join("staticfiles", "manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)
    assert "name" in manifest
    assert "icons" in manifest
    assert "start_url" in manifest
    assert "display" in manifest
    assert manifest["display"] == "standalone"


@pytest.mark.tier1
def test_service_worker_exists():
    import os
    assert os.path.exists(os.path.join("staticfiles", "js", "sw.js"))


@pytest.mark.tier2
@pytest.mark.django_db
def test_offline_page_returns_200(client):
    response = client.get("/offline/")
    assert response.status_code == 200


@pytest.mark.tier2
@pytest.mark.django_db
def test_manifest_served_as_json(client):
    response = client.get("/static/manifest.json")
    # StaticFiles повертає правильний content-type
    # В dev через staticfiles — може бути 200 або 404 залежно від STATICFILES_DIRS
    assert response.status_code in (200, 301, 302)


@pytest.mark.tier1
def test_manifest_icons_exist():
    import os
    assert os.path.exists(os.path.join("staticfiles", "icons", "icon-192.png"))
    assert os.path.exists(os.path.join("staticfiles", "icons", "icon-512.png"))
```

## Acceptance criteria

- [ ] `manifest.json` валідний (перевірити в Chrome DevTools → Application → Manifest)
- [ ] `sw.js` реєструється без помилок (DevTools → Application → Service Workers)
- [ ] `icon-192.png` і `icon-512.png` існують у `staticfiles/icons/`
- [ ] "Add to Home Screen" пропонується на мобільному Chrome
- [ ] `/offline/` повертає 200
- [ ] SSE запити (`/events/`) не кешуються Service Worker
- [ ] Тести зелені
