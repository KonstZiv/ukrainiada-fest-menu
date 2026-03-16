/**
 * Festival Menu Service Worker
 * Caches static assets and menu pages for offline access.
 * Strategy: network-first with cache fallback.
 */

const CACHE_NAME = "festival-menu-v1";

const PRECACHE_URLS = [
    "/menu/",
    "/static/css/brand.css",
    "/static/js/sse_client.js",
    "/static/icons/icon-192.png",
    "/static/manifest.json",
    "/offline/",
];

// Install: precache critical resources
self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(PRECACHE_URLS);
        }),
    );
    self.skipWaiting();
});

// Activate: remove old caches
self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)),
            ),
        ),
    );
    self.clients.claim();
});

// Fetch: network first, cache fallback
self.addEventListener("fetch", (event) => {
    // Never cache SSE streams
    if (event.request.url.includes("/events/")) {
        return;
    }

    // Never cache POST requests
    if (event.request.method !== "GET") {
        return;
    }

    event.respondWith(
        fetch(event.request)
            .then((response) => {
                if (response.ok) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, clone);
                    });
                }
                return response;
            })
            .catch(() => {
                return caches.match(event.request).then((cached) => {
                    if (cached) {
                        return cached;
                    }
                    return caches.match("/offline/");
                });
            }),
    );
});
