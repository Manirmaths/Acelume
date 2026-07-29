// Acelume service worker -- hand-rolled (no build plugin) so it stays
// simple and doesn't add a new build dependency. Two jobs:
//   1. Cache the app shell + static assets so the site is installable and
//      still opens (with cached UI) when offline.
//   2. Display push notifications sent by the backend (see
//      backend/app/routers/notifications.py).
//
// NOT cached: anything under /api/ -- this is a practice app, serving stale
// quiz/dashboard data offline would be actively misleading, so API calls
// always hit the network and the app's existing error states handle failure.
const CACHE_VERSION = 'v2';
const CACHE_NAME = `naijaprep-${CACHE_VERSION}`;
const APP_SHELL = [
  '/', '/manifest.webmanifest', '/favicon.svg', '/icons/icon-192.png', '/icons/icon-512.png',
  '/offline.html',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;

  // SPA navigations: network-first, fall back to the cached shell offline,
  // and if even that isn't cached yet (first-ever visit with no connection),
  // a static offline.html instead of the browser's generic error page.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put('/', copy));
          return res;
        })
        .catch(() => caches.match('/').then((cached) => cached || caches.match('/offline.html')))
    );
    return;
  }

  // Static assets (hashed JS/CSS/images/fonts): stale-while-revalidate --
  // instant from cache if present, refreshed in the background.
  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request)
        .then((res) => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return res;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});

self.addEventListener('push', (event) => {
  if (!event.data) return;
  let payload;
  try {
    payload = event.data.json();
  } catch {
    payload = { title: 'Acelume', body: event.data.text() };
  }
  event.waitUntil(
    self.registration.showNotification(payload.title || 'Acelume', {
      body: payload.body || '',
      icon: '/icons/icon-192.png',
      badge: '/icons/icon-192.png',
      data: { url: payload.url || '/dashboard' },
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/dashboard';
  event.waitUntil(
    self.clients.matchAll({ type: 'window' }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes(url) && 'focus' in client) return client.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
