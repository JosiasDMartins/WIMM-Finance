// Service Worker for SweetMoney PWA
// Version: {{ db_version }}
// Purpose: Cache static assets for performance, display offline page when server unreachable
// IMPORTANT: HTML pages are NEVER cached - always fetched from server to ensure updates

const CACHE_VERSION = 'sweetmoney-cache-v{{ cache_version }}';
const SERVER_VERSION = '{{ db_version }}';

const CACHE_ASSETS = [
    '/static/finances/css/tailwind.css',
    '/static/finances/css/fonts.css',
    '/static/finances/images/logo.png',
    '/static/finances/images/favicons/android-chrome-192x192.png',
    '/static/finances/images/favicons/android-chrome-512x512.png',
    '/static/finances/images/favicons/apple-touch-icon.png',
    '/offline/',  // Offline page only
];

// Install event - cache essential assets
self.addEventListener('install', (event) => {
    console.log('[ServiceWorker v{{ db_version }}] Installing...');

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

// Activate event - clean up old caches AGGRESSIVELY
self.addEventListener('activate', (event) => {
    console.log('[ServiceWorker v{{ db_version }}] Activating...');
    console.log('[ServiceWorker] Current cache version:', CACHE_VERSION);

    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                console.log('[ServiceWorker] Found caches:', cacheNames);

                // Delete ALL caches that don't match current version
                const deletePromises = cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_VERSION) {
                        console.log('[ServiceWorker] ❌ DELETING old cache:', cacheName);
                        return caches.delete(cacheName);
                    } else {
                        console.log('[ServiceWorker] ✓ Keeping current cache:', cacheName);
                        return Promise.resolve();
                    }
                });

                return Promise.all(deletePromises);
            })
            .then(() => {
                console.log('[ServiceWorker] ✅ Cache cleanup complete');
                console.log('[ServiceWorker] ✅ Taking control of all clients');
                return self.clients.claim();
            })
            .then(() => {
                console.log('[ServiceWorker] ✅ Activation complete for version {{ db_version }}');
            })
    );
});

// Fetch event - Network-first strategy with intelligent caching
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

    // CRITICAL: NEVER cache HTML pages - always fetch from server
    const isHTMLPage = request.headers.get('accept')?.includes('text/html') && !url.pathname.startsWith('/static/');

    if (isHTMLPage) {
        // HTML pages: Network-only (except offline page)
        event.respondWith(
            fetch(request)
                .catch(() => {
                    // Only if network fails, show offline page
                    return caches.match('/offline/');
                })
        );
        return;
    }

    // For static assets: Network-first with cache fallback
    event.respondWith(
        fetch(request)
            .then((response) => {
                // If response is valid, clone it and update cache
                if (response && response.status === 200) {
                    const responseClone = response.clone();

                    // Only cache static assets (CSS, JS, images, fonts)
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
                // Network failed, try cache for static assets
                return caches.match(request)
                    .then((cachedResponse) => {
                        if (cachedResponse) {
                            console.log('[ServiceWorker] Serving from cache:', request.url);
                            return cachedResponse;
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
