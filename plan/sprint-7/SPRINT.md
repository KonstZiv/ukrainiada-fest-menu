# Sprint 7 — Responsive UI, PWA, Touch-friendly

## Board

**Мета:** зручний інтерфейс на трьох типах пристроїв (смартфон, планшет, ноутбук) для всіх ролей. PWA для "Add to Home Screen". Touch-friendly для кухні та офіціантів.
**Оцінка:** 10–12 годин
**Залежності:** Sprint 6 завершений
**Статус:** ✅ ЗАВЕРШЕНО, merged to dev (pending main merge)

| # | Назва | Оцінка | Статус |
|---|---|---|---|
| 7.1 | Responsive visitor: menu, cart, dish detail | 2.5 год | ✅ Done |
| 7.2 | Responsive staff dashboards (kitchen, waiter, manager) | 3 год | ✅ Done |
| 7.3 | PWA manifest і service worker | 2 год | ✅ Done |
| 7.4 | Offline UX і cache | 2 год | ✅ Done |

---

## Три breakpoints

| Breakpoint | Ширина | Пристрій | Характеристика |
|-----------|--------|----------|----------------|
| `< md` | < 768px | Смартфон | Одна рука, вертикальний стек, великі кнопки |
| `md–lg` | 768–991px | Планшет | Touch, 2 колонки, більше інфо на картці |
| `≥ lg` | ≥ 992px | Ноутбук/десктоп | Миша, kanban/таблиці, повна інформація |

## Touch-friendly правила (реалізовано)

- Смартфон + планшет (< lg): `.btn-action` — `min-height: 48px`
- Кухня (**всі розміри**, включно з desktop): `.btn-kitchen-action` — `min-height: 56px` (брудні/мокрі руки, тачскрін на стаціонарі)
- Між інтерактивними елементами: Bootstrap `gap-2` (8px)
- На mobile: кухонні кнопки `width: 100%` для зручності
- `font-size: 16px` мінімум (запобігає zoom на iOS)

## Layout по ролях (реалізовано)

| Роль | Смартфон (< md) | Планшет (md–lg) | Ноутбук (≥ lg) |
|------|----------------|-----------------|----------------|
| **Visitor** | 1 колонка карток | 2 колонки | 3 колонки |
| **Kitchen** | Вертикальний стек секцій | 2 колонки kanban | 3 колонки kanban (Черга \| В роботі \| Готово) |
| **Waiter** | Картки замовлень | Картки з більше деталей | Таблиця з повною інфо |

## Що реалізовано

### Tasks 7.1 + 7.2 — Responsive CSS + Templates

**brand.css (нові правила):**
- `@media (max-width: 991.98px)` — `.btn-action` touch targets 48px
- `.btn-kitchen-action` — 56px на всіх розмірах (base rule, не media query)
- `.kitchen-kanban` — CSS Grid: `1fr` → `1fr 1fr` (md) → `1fr 1fr 1fr` (lg)
- `.ticket-card-pending/taken/done/escalated` — кольорові border-left по статусу
- `@keyframes pulse-border` — пульсуюча анімація для ескальованих тікетів
- `.waiter-order-table` / `.waiter-order-cards` — переключення table↔cards по breakpoint
- `.detail-md`, `.detail-lg` — додаткова інфо видима тільки на tablet+/desktop
- `.list-group-item` збільшені padding на touch

**Kitchen dashboard (templates/kitchen/dashboard.html):**
- Kanban grid layout з `kitchen-kanban` class
- 3 kanban-col: Черга (warning), В роботі (info), Готово (success)
- Ticket cards з кольоровими border-left
- `.detail-md` — час у черзі, `.detail-lg` — ім'я офіціанта (hidden on mobile)
- Handoff кнопки: `btn-kitchen-action` (56px), текст прихований на mobile (`d-none d-md-inline`)

**Waiter dashboard (templates/orders/waiter_dashboard.html):**
- Desktop (≥ lg): `waiter-order-table` — повна таблиця (статус, страви, кухня, сума, оплата, дії)
- Mobile/tablet: `waiter-order-cards` — компактні картки
- Ticket status badges (0.8rem font-size)

**Dish list + Search (templates/menu/):**
- Responsive grid: `col-12 col-md-6 col-lg-4`
- `container-fluid` замість `container` для максимального використання ширини

### Task 7.3 — PWA

**manifest.json (staticfiles/):**
- `name`: "Festival Menu — Ukrainiada"
- `display`: "standalone"
- `theme_color`: "#004A7A" (brand primary)
- `start_url`: "/menu/"
- Icons: 192×192 + 512×512 (generated via Pillow, Ukrainian flag motif)

**Service Worker (staticfiles/js/sw.js):**
- Стратегія: network-first з cache fallback
- Precache: `/menu/`, `/offline/`, CSS, JS, icons, manifest
- Виключення: SSE (`/events/`), POST запити
- Activate: автоматичне видалення старих кешів

**base.html інтеграція:**
- `<meta name="theme-color">`
- `<link rel="manifest">`
- SW реєстрація через `navigator.serviceWorker.register()`

### Task 7.4 — Offline UX

**offline_detector.js (staticfiles/js/):**
- Sticky banner при втраті мережі (alert-warning)
- Блокує кнопки submit у формах з класом `.form-needs-network`
- Автоматичне відновлення при reconnect (banner зникає, кнопки активуються)
- Підключено через `defer` в base.html

**Offline page (templates/offline.html):**
- Standalone HTML (не залежить від base.html — кешується SW окремо)
- Кнопка "Спробувати знову" (touch-friendly 48px)
- View: `core_settings.views.offline_page` → `/offline/`

### Тести
- core_settings/tests_pwa.py — 8 тестів (manifest validation, file existence, offline page, template integration)

## Відкладено на майбутнє

- [ ] **Темна тема для staff** — кухня під сонцем, екран має бути читабельним. Потребує окремий CSS файл або CSS variables toggle. Не реалізовано в цьому спринті
- [ ] **CSS модуляризація** — brand.css ~370 рядків, поки допустимо. Коли перевищить ~500 рядків → розділити на окремі файли (base, kitchen, waiter, visitor) або впровадити Sass
- [ ] **`base_visitor.html` / `base_staff.html`** — окремі base шаблони для відвідувачів та staff (різні header, footer, скрипти). Зараз все через один `base.html`
- [ ] **Cache-Control headers** на `/menu/` view (plan task 7.4 мав `max-age=300`)
- [ ] **Background sync** в SW — оновлення меню коли з'являється мережа
- [ ] **Lighthouse PWA score ≥ 80** — потребує HTTPS (production deployment)
- [ ] **E2E тести** (tier3) для offline mode через Playwright
- [ ] **Manager/Senior waiter dashboard** — responsive layout (зараз не оновлено, потребує окремої роботи)

## Definition of Done ✅

- [x] Всі сторінки responsive (3 breakpoints) без горизонтального скролу
- [x] Touch targets ≥ 48px на смартфоні/планшеті, ≥ 56px для кухні (всі розміри)
- [x] Kitchen dashboard: kanban на ≥ lg, 2 колонки на md, стек на < md
- [x] Waiter dashboard: table на desktop, cards на mobile/tablet
- [x] Dish list/search: responsive grid 1/2/3 колонки
- [x] `manifest.json` валідний з іконками
- [x] Service worker: network-first, precache, offline fallback
- [x] Offline banner + form blocking
- [x] `/offline/` fallback page
- [x] Всі тести зелені
