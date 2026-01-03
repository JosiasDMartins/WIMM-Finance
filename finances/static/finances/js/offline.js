// ============================================
// OFFLINE.JS - PHASE 3 CSP COMPLIANCE
// ============================================
// Auto-retry connection when offline
// Version: 20251231-001
// Extracted from: offline.html

(function() {
    'use strict';

    let retryCount = 0;
    const maxRetries = 60; // Try for 10 minutes (60 retries x 10 seconds)

    // Retry connection function
    window.retryConnection = function() {
        retryCount = 0; // Reset counter on manual retry
        checkConnection();
    };

    // Check connection
    function checkConnection() {
        fetch('/', { method: 'HEAD', cache: 'no-cache' })
            .then(response => {
                if (response.ok) {
                    console.log('[Offline] Server is back online, redirecting...');
                    window.location.href = '/';
                }
            })
            .catch(error => {
                console.log('[Offline] Still offline, retry', retryCount, '/', maxRetries);
            });
    }

    // Auto-retry every 10 seconds
    const autoRetryInterval = setInterval(() => {
        retryCount++;

        if (retryCount >= maxRetries) {
            clearInterval(autoRetryInterval);
            const status = document.getElementById('connection-status');
            const config = document.getElementById('offline-config');
            const stillCantConnect = config ? (config.dataset.i18nStillCantConnect || "😢 Still can't connect. Try the button!") : "😢 Still can't connect. Try the button!";

            if (status) {
                status.innerHTML = `
                    <div class="inline-flex items-center gap-2 px-4 py-2 bg-red-50 dark:bg-red-900/20 rounded-lg">
                        <span class="inline-block w-2 h-2 bg-red-500 rounded-full"></span>
                        <span class="text-sm text-red-700 dark:text-red-400 font-medium">
                            ${stillCantConnect}
                        </span>
                    </div>
                `;
            }
            return;
        }

        checkConnection();
    }, 10000); // Every 10 seconds

    // Attach retry handler to button
    const retryButton = document.querySelector('[data-action="retry-connection"]');
    if (retryButton) {
        retryButton.addEventListener('click', window.retryConnection);
    }

    console.log('[Offline] Offline page loaded, will auto-retry every 10 seconds');
})();
