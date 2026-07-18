const CACHE_NAME = 'hardcore-fashion-v2';
const OFFLINE_URL = '/offline/';

const STATIC_ASSETS = [
  '/',
  '/static/css/style.css',
  '/static/css/products.css',
  '/static/css/checkout.css',
  '/static/js/main.js',
  '/static/manifest.json',
  OFFLINE_URL,
];

// Install: pre-cache static assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// Activate: remove old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// Fetch strategy:
// - Static assets (CSS/JS/images): cache-first
// - API calls: network-only
// - HTML pages: stale-while-revalidate, fallback to offline page
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET and cross-origin requests
  if (request.method !== 'GET' || url.origin !== location.origin) return;

  // API: network-only
  if (url.pathname.startsWith('/api/')) return;

  // Static assets: cache-first
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then(cached => cached || fetch(request).then(res => {
        const clone = res.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
        return res;
      }))
    );
    return;
  }

  // HTML pages: stale-while-revalidate with offline fallback
  event.respondWith(
    caches.open(CACHE_NAME).then(cache =>
      cache.match(request).then(cached => {
        const networkFetch = fetch(request).then(res => {
          cache.put(request, res.clone());
          return res;
        }).catch(() => caches.match(OFFLINE_URL));
        return cached || networkFetch;
      })
    )
  );
});
