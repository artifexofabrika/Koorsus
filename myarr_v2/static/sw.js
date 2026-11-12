// Myarra PWA service worker.
// Caches only the shell. Never caches API responses or Herbie answers,
// because those must always reflect the live database.

const CACHE_NAME = 'myarra-shell-v1';
const SHELL_URLS = ['/floor', '/static/style.css', '/static/manifest.json'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_URLS).catch(() => null))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  // Never cache POST, never cache /api or /herbie or /floor POST.
  if (event.request.method !== 'GET') return;
  if (url.pathname.startsWith('/api/')) return;
  // Cache-first for static assets and shell pages only.
  if (url.pathname.startsWith('/static/') || url.pathname === '/floor') {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          return resp;
        });
      })
    );
  }
});
