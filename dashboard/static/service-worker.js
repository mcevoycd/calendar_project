const CACHE_VERSION = 'v3';
const STATIC_CACHE = `fluid-notes-static-${CACHE_VERSION}`;
const PAGE_CACHE = `fluid-notes-pages-${CACHE_VERSION}`;
const API_CACHE = `fluid-notes-api-${CACHE_VERSION}`;
const ALL_CACHES = [STATIC_CACHE, PAGE_CACHE, API_CACHE];

const CORE_ASSETS = [
  '/manifest.json',
  '/icons/icon-180.png',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/static/dashboard/offline.html'
];

function isSameOrigin(requestUrl) {
  try {
    return new URL(requestUrl).origin === self.location.origin;
  } catch (error) {
    return false;
  }
}

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) {
    return cached;
  }

  const response = await fetch(request);
  if (response && response.ok) {
    cache.put(request, response.clone());
  }
  return response;
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const networkPromise = fetch(request)
    .then((response) => {
      if (response && response.ok) {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => null);

  if (cached) {
    return cached;
  }

  const networkResponse = await networkPromise;
  if (networkResponse) {
    return networkResponse;
  }

  throw new Error('No cached or network response available');
}

async function networkFirst(request, cacheName, fallbackRequest) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) {
      return cached;
    }
    if (fallbackRequest) {
      const fallback = await caches.match(fallbackRequest);
      if (fallback) {
        return fallback;
      }
    }
    throw error;
  }
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => cache.addAll(CORE_ASSETS).catch(() => Promise.resolve()))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => !ALL_CACHES.includes(key)).map((key) => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') {
    return;
  }

  if (!isSameOrigin(request.url)) {
    return;
  }

  const url = new URL(request.url);

  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request, PAGE_CACHE, '/static/dashboard/offline.html'));
    return;
  }

  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request, API_CACHE));
    return;
  }

  if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/icons/')) {
    event.respondWith(staleWhileRevalidate(request, STATIC_CACHE));
    return;
  }

  event.respondWith(cacheFirst(request, STATIC_CACHE));
});
