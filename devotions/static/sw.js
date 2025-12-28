const CACHE_NAME = 'prayer-app-v5';
const ASSETS_TO_CACHE =
    ['/static/styles.css', '/static/favicon.svg', '/static/banner.jpg'];

// Install event: Cache static assets
self.addEventListener('install', (event) => {
  self.skipWaiting();  // Activate worker immediately
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => {
    return cache.addAll(ASSETS_TO_CACHE);
  }));
});

// Activate event: Clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
      caches.keys()
          .then((cacheNames) => {
            return Promise.all(cacheNames.map((cacheName) => {
              if (cacheName !== CACHE_NAME) {
                return caches.delete(cacheName);
              }
            }));
          })
          .then(() => self.clients.claim())  // Become available to all pages
  );
});

// Fetch event: Serve from cache if available, otherwise fetch from network
self.addEventListener('fetch', (event) => {
  // For navigation requests (HTML pages), try network first, then cache
  // This ensures users get the latest daily devotion content if online
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request)
                          .then((response) => {
                            // Update cache with the latest version
                            if (response && response.status === 200 &&
                                response.type === 'basic') {
                              const responseToCache = response.clone();
                              caches.open(CACHE_NAME).then((cache) => {
                                cache.put(event.request, responseToCache);
                              });
                            }
                            return response;
                          })
                          .catch(() => {
                            return caches.match(event.request);
                          }));
  } else {
    // For other assets (CSS, images), try cache first, then network
    event.respondWith(caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    }));
  }
});
