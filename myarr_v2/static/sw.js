// Myarra PWA service worker.
// Caches only the shell. Never caches API responses or Herbie answers,
// because those must always reflect the live database.
//
// v2, 2026-11-22 (A49). v1 served /floor cache-first, so once a device had
// seen the page it served itself that page forever and never revalidated.
// The floor forms carry job_number and period in hidden fields, so a frozen
// page posts the job and the hour that were true when it was cached: an hour
// written against a job that ended days ago, no error, no trace. The cache
// name is bumped so every device purges v1 on its next activation.

const CACHE_NAME = 'myarra-shell-v2';
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

// Always resolves to a Response. respondWith() with undefined throws, and an
// offline device with an empty cache is exactly the case that would hit it.
function offlineFallback(request) {
  return caches.match(request).then((cached) => {
    if (cached) return cached;
    return new Response('Offline, and this page is not cached yet.', {
      status: 503,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' }
    });
  });
}

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // A POST is never cached, and neither is anything that answers from the
  // live database. Both fall straight through to the network.
  if (event.request.method !== 'GET') return;
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;

  if (url.pathname === '/floor') {
    // Network first. The page shows which line is running what and carries
    // hidden job fields, so it must be fetched fresh every navigation. The
    // cached copy is only there so an offline device shows the last floor it
    // saw instead of a blank screen, and offline it cannot post anyway.
    event.respondWith(
      fetch(event.request)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          return resp;
        })
        .catch(() => offlineFallback(event.request))
    );
    return;
  }

  if (url.pathname.startsWith('/static/')) {
    // Cache first. Icons and CSS do not change between deploys, and when they
    // do, CACHE_NAME is bumped and activate deletes the old cache.
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          return resp;
        }).catch(() => offlineFallback(event.request));
      })
    );
  }
});
