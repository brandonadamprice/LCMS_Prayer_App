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

self.addEventListener('push', function(event) {
  if (event.data) {
    const payload = event.data.json();
    // payload.data contains the custom fields sent from the server
    const data = payload.data || {}; 
    const title = data.title || "Prayer Reminder";
    const body = data.body || "It's time for prayer.";
    const url = data.url || "/";

    const options = {
      body: body,
      icon: '/static/favicon.svg',
      badge: '/static/favicon.svg',
      data: {
        url: url
      }
    };
    event.waitUntil(
      self.registration.showNotification(title, options)
    );
  }
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({type: 'window'}).then( windowClients => {
        for (var i = 0; i < windowClients.length; i++) {
            var client = windowClients[i];
            if (client.url === event.notification.data.url && 'focus' in client) {
                return client.focus();
            }
        }
        if (clients.openWindow) {
            return clients.openWindow(event.notification.data.url);
        }
    })
  );
});
