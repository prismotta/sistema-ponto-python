/* Basic PWA service worker for Sistema de Ponto */

const CACHE_NAME = "ponto-pwa-v3";
const PRECACHE_URLS = [
  "/",
  "/manifest.json",
  "/static/icons/icon-192.svg",
  "/static/icons/icon-512.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.map((k) => (k === CACHE_NAME ? Promise.resolve() : caches.delete(k))))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Only handle same-origin GET requests
  if (request.method !== "GET") return;
  if (url.origin !== self.location.origin) return;

  // Do not cache state-changing endpoints or exports
  const networkOnlyPrefixes = ["/bater", "/logout", "/export/", "/api/"];
  if (networkOnlyPrefixes.some((p) => url.pathname.startsWith(p))) {
    event.respondWith(fetch(request));
    return;
  }

  // Static assets: cache-first
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        return resp;
      }))
    );
    return;
  }

  // Navigation/pages: network-first with fallback
  if (request.mode === "navigate" || request.headers.get("accept")?.includes("text/html")) {
    event.respondWith(
      fetch(request)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          return resp;
        })
        .catch(() => caches.match(request).then((cached) => cached || caches.match("/")))
    );
    return;
  }

  // Default: try network, fallback to cache
  event.respondWith(fetch(request).catch(() => caches.match(request)));
});
