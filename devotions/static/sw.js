const CACHE_NAME = 'prayer-app-v23';
const ASSETS_TO_CACHE = [
  '/static/styles.css',
  '/static/banner.jpg',
  '/static/icons/favicon.ico',
  '/static/icons/android-chrome-192x192.png',
  '/static/icons/android-chrome-512x512.png'
];

// Install event: Cache static assets
self.addEventListener('install', (event) => {
  // Force the waiting service worker to become the active service worker.
  self.skipWaiting();
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
  const url = new URL(event.request.url);

  // The service worker only handles GET. POST/PUT/etc. (API writes, form
  // submits, analytics beacons) go straight to the network -- Cache.put()
  // rejects on non-GET requests, which caused
  // "Failed to execute 'put' on 'Cache': Request method 'POST' is unsupported".
  if (event.request.method !== 'GET') {
    return;
  }

  // Exclude authentication routes from service worker interception.
  // This allows the browser to handle redirects and cookies for OAuth natively.
  // /__/ covers the proxied Firebase Auth helper (/__/auth, /__/firebase),
  // which runs in the sign-in popup on this origin and must never be cached.
  if (url.pathname.startsWith('/login') ||
      url.pathname.startsWith('/authorize') ||
      url.pathname.startsWith('/__/')) {
    return;
  }

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
    // Cross-origin requests (Google Fonts, CDN scripts, analytics) pass
    // straight through to the network -- never SW-mediated or cached -- so we
    // don't store opaque responses or add a hop to third-party fetches.
    if (url.origin !== self.location.origin) {
      return;
    }

    // For same-origin assets (CSS, JS, images): cache-first. Serve the cached
    // copy instantly when present (no network at all); otherwise fetch once and
    // cache it for next time / offline. We deliberately do NOT revalidate in
    // the background: doing so fired a network request for every asset on every
    // load, saturating the browser's ~6-connections-per-origin limit and
    // queueing the whole page behind it. Assets refresh when CACHE_NAME is
    // bumped on deploy (and styles.css via its ?v= query string).
    event.respondWith(
        caches.match(event.request).then((cached) => {
          if (cached) {
            return cached;
          }
          return fetch(event.request).then((response) => {
            if (response && response.ok && response.type === 'basic') {
              const copy = response.clone();
              event.waitUntil(
                  caches.open(CACHE_NAME).then((cache) =>
                      cache.put(event.request, copy)));
            }
            return response;
          });
        }));
  }
});

self.addEventListener('push', function(event) {
  if (event.data) {
    const payload = event.data.json();
    // payload.data contains the custom fields sent from the server
    const data = payload.data || {};
    const title = data.title || 'Prayer Reminder';
    const body = data.body || 'It\'s time for prayer.';
    const url = data.url || '/';

    const options = {
      body: body,
      icon: '/static/icons/android-chrome-192x192.png',
      badge: '/static/icons/android-chrome-192x192.png',
      data: {url: url}
    };
    event.waitUntil(self.registration.showNotification(title, options));
  }
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  // Ensure the URL is absolute relative to the SW's origin to avoid "out of
  // scope" issues (browser header) and to ensure reliable matching of existing
  // windows.
  const rawUrl = event.notification.data.url;
  const urlToOpen = new URL(rawUrl, self.location.origin).href;

  event.waitUntil(clients.matchAll({type: 'window', includeUncontrolled: true})
                      .then((windowClients) => {
                        let matchingClient = null;

                        // 1. Prioritize exact URL match
                        for (let i = 0; i < windowClients.length; i++) {
                          const client = windowClients[i];
                          if (client.url === urlToOpen) {
                            matchingClient = client;
                            break;
                          }
                        }

                        // 2. If no exact match, grab the first available window
                        if (!matchingClient && windowClients.length > 0) {
                          matchingClient = windowClients[0];
                        }

                        if (matchingClient) {
                          if (matchingClient.url !== urlToOpen) {
                            return matchingClient.navigate(urlToOpen).then(
                                client => client.focus());
                          } else {
                            return matchingClient.focus();
                          }
                        } else {
                          // 3. If no windows open, open a new one
                          if (clients.openWindow) {
                            return clients.openWindow(urlToOpen);
                          }
                        }
                      }));
});
