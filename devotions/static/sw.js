const CACHE_NAME = 'prayer-app-v1';
const ASSETS_TO_CACHE = [
  '/static/styles.css',
  '/static/favicon.svg',
  '/static/banner.jpg'
];

// Install event: Cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
});

// Fetch event: Serve from cache if available, otherwise fetch from network
self.addEventListener('fetch', (event) => {
  // For navigation requests (HTML pages), try network first, then cache
  // This ensures users get the latest daily devotion content if online
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => {
        return caches.match(event.request);
      })
    );
  } else {
    // For other assets (CSS, images), try cache first, then network
    event.respondWith(
      caches.match(event.request).then((response) => {
        return response || fetch(event.request);
      })
    );
  }
});
