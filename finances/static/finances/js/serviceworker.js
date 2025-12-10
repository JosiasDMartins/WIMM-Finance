// Service Worker for SweetMoney PWA
// Version: 1.0.0
// Purpose: Cache static assets for performance, display offline page when server unreachable

const CACHE_VERSION = 'sweetmoney-cache-v1';
const CACHE_ASSETS = [
    '/static/finances/css/tailwind.css',
    '/static/finances/css/fonts.css',
    '/static/finances/images/logo.png',
    '/static/finances/images/favicons/android-chrome-192x192.png',
    '/static/finances/images/favicons/android-chrome-512x512.png',
    '/static/finances/images/favicons/apple-touch-icon.png',
    '/offline/',  // Offline page
];

// Install event - cache essential assets
self.addEventListener('install', (event) => {
    console.log('[ServiceWorker] Installing...');

    event.waitUntil(
        caches.open(CACHE_VERSION)
            .then((cache) => {
                console.log('[ServiceWorker] Caching app shell');
                return cache.addAll(CACHE_ASSETS);
            })
            .then(() => {
                console.log('[ServiceWorker] Install complete');
                return self.skipWaiting();
            })
            .catch((error) => {
                console.error('[ServiceWorker] Install failed:', error);
            })
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    console.log('[ServiceWorker] Activating...');

    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames.map((cacheName) => {
                        if (cacheName !== CACHE_VERSION) {
                            console.log('[ServiceWorker] Removing old cache:', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            })
            .then(() => {
                console.log('[ServiceWorker] Activation complete');
                return self.clients.claim();
            })
    );
});

// Fetch event - Network-first strategy with cache fallback
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') {
        return;
    }

    // Skip chrome-extension and other non-http(s) requests
    if (!url.protocol.startsWith('http')) {
        return;
    }

    event.respondWith(
        fetch(request)
            .then((response) => {
                // If response is valid, clone it and update cache
                if (response && response.status === 200) {
                    const responseClone = response.clone();

                    // Only cache static assets
                    if (isStaticAsset(url.pathname)) {
                        caches.open(CACHE_VERSION)
                            .then((cache) => {
                                cache.put(request, responseClone);
                            });
                    }
                }
                return response;
            })
            .catch(() => {
                // Network failed, try cache
                return caches.match(request)
                    .then((cachedResponse) => {
                        if (cachedResponse) {
                            console.log('[ServiceWorker] Serving from cache:', request.url);
                            return cachedResponse;
                        }

                        // If HTML page and not in cache, show offline page
                        if (request.headers.get('accept').includes('text/html')) {
                            return caches.match('/offline/');
                        }

                        // For other resources, return a generic error
                        return new Response('Network error', {
                            status: 408,
                            headers: { 'Content-Type': 'text/plain' }
                        });
                    });
            })
    );
});

// Helper function to determine if URL is a static asset
function isStaticAsset(pathname) {
    const staticExtensions = ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.woff', '.woff2', '.ttf', '.eot'];
    return staticExtensions.some(ext => pathname.endsWith(ext)) || pathname.startsWith('/static/');
}

// Message event - handle messages from clients
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        console.log('[ServiceWorker] Received SKIP_WAITING message');
        self.skipWaiting();
    }
});
