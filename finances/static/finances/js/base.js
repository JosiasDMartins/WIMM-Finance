/**
 * Base Template JavaScript
 * External JavaScript file (CSP compliant - no inline scripts)
 * Handles: Dark mode, DPI scaling, Period management, Admin warning, Modals, PWA, WebSocket init, UI Components
 */

// ===== 1. DARK MODE INITIALIZATION (MUST RUN IMMEDIATELY - NO DOM WAIT) =====
// This prevents FOUC (Flash of Unstyled Content) on page load
(function() {
    'use strict';
    const htmlElement = document.documentElement;
    htmlElement.classList.remove('light');
    const saved = localStorage.getItem('theme');
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    const initial = saved ? saved : (prefersDark ? 'dark' : 'light');
    if (initial === 'dark') {
        htmlElement.classList.add('dark');
    }
})();

// ===== 2. DPI SCALING ADJUSTMENT (MUST RUN IMMEDIATELY) =====
(function() {
    'use strict';

    // Detect and adjust for Windows DPI scaling
    function adjustForDPIScaling() {
        const dpr = window.devicePixelRatio || 1;
        const screenWidth = window.screen.width * dpr;

        // If DPI scaling is detected (devicePixelRatio > 1) on a FullHD or smaller screen
        // Apply a slight zoom reduction to prevent UI elements from being cut off
        if (dpr >= 1.5 && screenWidth <= 1920) {
            // Calculate optimal zoom level
            const optimalZoom = Math.max(0.85, 1 / (dpr * 0.85));
            document.documentElement.style.zoom = optimalZoom;

            console.log('[DPI Adjust] Detected DPI scaling:', dpr, '| Applying zoom:', optimalZoom);
        }
    }

    // Run on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', adjustForDPIScaling);
    } else {
        adjustForDPIScaling();
    }

    // Re-adjust on window resize
    window.addEventListener('resize', function() {
        adjustForDPIScaling();
    });
})();

// ===== WAIT FOR DOM BEFORE CONTINUING =====
document.addEventListener('DOMContentLoaded', function() {
    'use strict';

    // ===== 3. LOAD CONFIGURATION FROM DATA ATTRIBUTES =====
    initializeBaseConfig();

    // ===== 4. ADMIN WARNING MODAL =====
    initializeAdminWarning();

    // ===== 5. CREATE PERIOD MODAL =====
    initializeCreatePeriodModal();

    // ===== 6. DELETE PERIOD MODAL =====
    initializeDeletePeriodModal();

    // ===== 7. DARK MODE TOGGLE =====
    initializeDarkModeToggle();

    // ===== 8. PWA SERVICE WORKER & VERSION MANAGEMENT =====
    initializePWA();

    // ===== 9. WEBSOCKET INITIALIZATION (if authenticated) =====
    initializeWebSocket();

    // ===== 10. UI COMPONENTS (Sidebar, Period Dropdown) =====
    initializeUIComponents();
});

// ===== 3. CONFIGURATION INITIALIZATION =====
function initializeBaseConfig() {
    const config = document.getElementById('base-config');
    if (!config) {
        console.warn('[Base] Configuration element not found - some features may not work');
        return;
    }

    // Translation strings for base.html JavaScript
    window.BASE_I18N = {
        errorLoadingPeriodDetails: config.dataset.i18nErrorLoadingPeriodDetails,
        errorLoadingPeriod: config.dataset.i18nErrorLoadingPeriod,
        pwaNewVersionTitle: config.dataset.i18nPwaNewVersionTitle,
        pwaInstalled: config.dataset.i18nPwaInstalled,
        pwaAvailable: config.dataset.i18nPwaAvailable,
        pwaUpdateInstructions: config.dataset.i18nPwaUpdateInstructions,
        pwaClickToDismiss: config.dataset.i18nPwaClickToDismiss,
        pwaIosInstructions: config.dataset.i18nPwaIosInstructions,
        pwaIosStep1: config.dataset.i18nPwaIosStep1,
        pwaIosStep2: config.dataset.i18nPwaIosStep2,
        pwaIosStep3: config.dataset.i18nPwaIosStep3
    };

    // Modal translations
    window.MODAL_I18N = {
        notification: config.dataset.i18nModalNotification,
        warning: config.dataset.i18nModalWarning,
        error: config.dataset.i18nModalError,
        success: config.dataset.i18nModalSuccess,
        confirm: config.dataset.i18nModalConfirm,
        ok: config.dataset.i18nModalOk,
        cancel: config.dataset.i18nModalCancel,
        continue: config.dataset.i18nModalContinue,
        yes: config.dataset.i18nModalYes,
        no: config.dataset.i18nModalNo,
        close: config.dataset.i18nModalClose
    };

    // Period management translations
    window.PERIOD_I18N = {
        creating: config.dataset.i18nPeriodCreating,
        errorCreating: config.dataset.i18nPeriodErrorCreating,
        confirmDelete: config.dataset.i18nPeriodConfirmDelete,
        deleting: config.dataset.i18nPeriodDeleting,
        errorDeleting: config.dataset.i18nPeriodErrorDeleting
    };

    // PWA config
    window.SERVER_VERSION = config.dataset.serverVersion;
    window.DB_VERSION = config.dataset.dbVersion;

    // User config (for WebSocket)
    window.USER_ID = config.dataset.userId;
    window.IS_AUTHENTICATED = config.dataset.isAuthenticated === 'true';

    // Locale settings (for realtime_ui.js)
    window.decimalSeparator = config.dataset.decimalSeparator;
    window.thousandSeparator = config.dataset.thousandSeparator;
    window.currencySymbol = config.dataset.currencySymbol;

    console.log('[Base] Configuration loaded');
}

// ===== 4. ADMIN WARNING MODAL =====
function initializeAdminWarning() {
    const modal = document.getElementById('admin-warning-modal');
    const btn = document.getElementById('btn-dismiss-admin-warning');

    if (btn && modal) {
        console.log('[Admin Warning] Button and modal found, adding event listener');
        btn.addEventListener('click', function() {
            console.log('[Admin Warning] "I Agree" button clicked');
            fetch('/mark-admin-warning-seen/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                }
            })
            .then(response => response.json())
            .then(data => {
                console.log('[Admin Warning] Server response:', data);
                if (data.status === 'ok') {
                    console.log('[Admin Warning] Modal dismissed successfully');
                    modal.remove();
                } else {
                    console.warn('[Admin Warning] Unexpected response, removing modal anyway');
                    modal.remove();
                }
            })
            .catch(error => {
                console.error('[Admin Warning] Error marking admin warning as seen:', error);
                modal.remove(); // Remove anyway to not block UI
            });
        });
    } else if (modal && !btn) {
        // Modal exists but button is missing - this is an error in the template
        console.warn('[Admin Warning] Modal exists but dismiss button not found!');
    }
    // If neither exist, that's normal - user has already seen the warning or is not admin
}

// ===== 5. CREATE PERIOD MODAL FUNCTIONS =====
function initializeCreatePeriodModal() {
    const form = document.getElementById('createPeriodForm');
    if (!form) return;

    const startDateInput = document.getElementById('period_start_date');
    const endDateInput = document.getElementById('period_end_date');

    if (startDateInput && endDateInput) {
        startDateInput.addEventListener('change', validatePeriodOverlap);
        endDateInput.addEventListener('change', validatePeriodOverlap);
    }

    form.addEventListener('submit', handleCreatePeriodSubmit);
}

// Exposed globally for event_delegation.js
window.openCreatePeriodModal = function() {
    document.getElementById('createPeriodModal').classList.remove('hidden');
    // Reset form
    document.getElementById('createPeriodForm').reset();
    document.getElementById('overlapWarning').classList.add('hidden');
    document.getElementById('createPeriodBtn').disabled = false;
};

window.closeCreatePeriodModal = function() {
    document.getElementById('createPeriodModal').classList.add('hidden');
};

function validatePeriodOverlap() {
    const startDate = document.getElementById('period_start_date').value;
    const endDate = document.getElementById('period_end_date').value;
    const warningDiv = document.getElementById('overlapWarning');
    const createBtn = document.getElementById('createPeriodBtn');

    if (!startDate || !endDate) {
        warningDiv.classList.add('hidden');
        createBtn.disabled = false;
        return;
    }

    fetch('/api/period/validate-overlap/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            start_date: startDate,
            end_date: endDate
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.has_overlap) {
            warningDiv.classList.remove('hidden');
            document.getElementById('overlapMessage').textContent = data.message;
            createBtn.disabled = true;
            createBtn.classList.add('bg-gray-400', 'cursor-not-allowed');
            createBtn.classList.remove('bg-green-600', 'hover:bg-green-700');
        } else {
            warningDiv.classList.add('hidden');
            createBtn.disabled = false;
            createBtn.classList.remove('bg-gray-400', 'cursor-not-allowed');
            createBtn.classList.add('bg-green-600', 'hover:bg-green-700');
        }
    })
    .catch(error => {
        console.error('Error validating period:', error);
    });
}

function handleCreatePeriodSubmit(e) {
    e.preventDefault();

    const startDate = document.getElementById('period_start_date').value;
    const endDate = document.getElementById('period_end_date').value;
    const createBtn = document.getElementById('createPeriodBtn');

    // Disable button during submission
    createBtn.disabled = true;
    createBtn.textContent = window.PERIOD_I18N.creating;

    fetch('/api/period/create/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            start_date: startDate,
            end_date: endDate
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Redirect to the new period
            window.location.href = data.redirect_url;
        } else {
            alert(window.PERIOD_I18N.errorCreating + ': ' + data.error);
            createBtn.disabled = false;
            createBtn.textContent = window.MODAL_I18N.continue;
        }
    })
    .catch(error => {
        console.error('Error creating period:', error);
        alert(window.PERIOD_I18N.errorCreating);
        createBtn.disabled = false;
        createBtn.textContent = window.MODAL_I18N.continue;
    });
}

// ===== 6. DELETE PERIOD MODAL FUNCTIONS =====
function initializeDeletePeriodModal() {
    // Modal functions are called by event_delegation.js
    // Nothing to initialize here
}

// Exposed globally for event_delegation.js
window.openDeletePeriodModal = function(periodId) {
    const modal = document.getElementById('deletePeriodModal');
    modal.classList.remove('hidden');
    modal.dataset.periodId = periodId;
};

window.closeDeletePeriodModal = function() {
    const modal = document.getElementById('deletePeriodModal');
    modal.classList.add('hidden');
    delete modal.dataset.periodId;
};

window.confirmDeletePeriod = function() {
    const modal = document.getElementById('deletePeriodModal');
    const periodId = modal.dataset.periodId;
    const confirmBtn = document.getElementById('confirmDeletePeriodBtn');
    const deleteButtonText = confirmBtn.querySelector('#deleteButtonText');
    const deleteButtonIcon = confirmBtn.querySelector('#deleteButtonIcon');

    if (!periodId) {
        console.error('No period ID found');
        return;
    }

    // Disable button and show loading state
    const originalText = deleteButtonText.textContent;
    confirmBtn.disabled = true;
    confirmBtn.style.cursor = 'wait';
    deleteButtonText.textContent = window.PERIOD_I18N.deleting;
    deleteButtonIcon.textContent = 'progress_activity';
    deleteButtonIcon.classList.add('animate-spin');

    fetch(`/api/period/${periodId}/delete/`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Redirect to the default period or home
            window.location.href = data.redirect_url || '/';
        } else {
            alert(window.PERIOD_I18N.errorDeleting + ': ' + data.error);
            confirmBtn.disabled = false;
            deleteButtonText.textContent = originalText;
            deleteButtonIcon.textContent = 'delete';
            deleteButtonIcon.classList.remove('animate-spin');
            confirmBtn.style.cursor = 'pointer';
        }
    })
    .catch(error => {
        console.error('Error deleting period:', error);
        alert(window.PERIOD_I18N.errorDeleting);
        confirmBtn.disabled = false;
        confirmBtn.querySelector('#deleteButtonText').textContent = originalText;
        confirmBtn.style.cursor = 'pointer';
    });
};

// ===== 7. DARK MODE TOGGLE =====
function initializeDarkModeToggle() {
    const themeToggle = document.getElementById('theme-toggle');
    const htmlElement = document.documentElement;
    const iconDark = document.getElementById('icon-dark');
    const iconLight = document.getElementById('icon-light');

    function setIcons() {
        if (!iconDark || !iconLight) return;
        if (htmlElement.classList.contains('dark')) {
            iconDark.style.display = 'none';
            iconLight.style.display = 'inline-block';
        } else {
            iconDark.style.display = 'inline-block';
            iconLight.style.display = 'none';
        }
    }

    // Apply immediately
    setIcons();

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            htmlElement.classList.toggle('dark');
            const newTheme = htmlElement.classList.contains('dark') ? 'dark' : 'light';
            localStorage.setItem('theme', newTheme);
            setIcons();
        });
    }
}

// ===== 8. GENERIC MODAL MANAGER =====
// MOVED TO: generic_modal.js (loaded separately for better organization)
// GenericModal provides alert() and confirm() methods via Promise-based API

// ===== 9. PWA SERVICE WORKER & VERSION MANAGEMENT =====
function initializePWA() {
    const SERVER_VERSION = window.SERVER_VERSION || window.DB_VERSION;

    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            // Check if running as installed PWA
            const isInstalled = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone;

            // Register service worker
            const swUrl = document.querySelector('meta[name="service-worker-url"]')?.content || '/service-worker.js';
            navigator.serviceWorker.register(swUrl)
                .then((registration) => {
                    console.log('[PWA] Service Worker registered successfully:', registration.scope);
                    console.log('[PWA] Server version: ' + SERVER_VERSION);

                    // Check for manifest version updates (for installed apps)
                    if (isInstalled) {
                        checkManifestVersion();
                    }

                    // Check for updates periodically
                    setInterval(() => {
                        registration.update();
                        if (isInstalled) {
                            checkManifestVersion();
                        }
                    }, 60000); // Check every minute
                })
                .catch((error) => {
                    console.error('[PWA] Service Worker registration failed:', error);
                });

            // Listen for service worker updates
            navigator.serviceWorker.addEventListener('controllerchange', () => {
                console.log('[PWA] New service worker activated - reloading page');
                window.location.reload();
            });
        });
    }

    // Check manifest version and prompt for reinstall if needed
    function checkManifestVersion() {
        try {
            // Get cached installed version
            const installedVersion = localStorage.getItem('pwa_installed_version');

            if (!installedVersion) {
                // First time running, save current version
                localStorage.setItem('pwa_installed_version', SERVER_VERSION);
                console.log('[PWA] Saved installed version: ' + SERVER_VERSION);
                return;
            }

            // Compare versions
            if (installedVersion !== SERVER_VERSION) {
                console.log('[PWA] Version mismatch! Installed: ' + installedVersion + ', Server: ' + SERVER_VERSION);

                // Show update notification
                showUpdateNotification(installedVersion, SERVER_VERSION);
            }
        } catch (error) {
            console.error('[PWA] Error checking manifest version:', error);
        }
    }

    function showUpdateNotification(oldVersion, newVersion) {
        // Only show once per version
        const notificationShown = sessionStorage.getItem('update_notification_' + newVersion);
        if (notificationShown) {
            return;
        }

        // Mark as shown
        sessionStorage.setItem('update_notification_' + newVersion, 'true');

        // Use existing modal system if available
        if (typeof window.showModal === 'function') {
            const title = '🎉 New Version Available!';
            const content = `
                <div class="space-y-4">
                    <p class="text-gray-700 dark:text-gray-300">
                        SweetMoney has been updated from <strong>v${oldVersion}</strong> to <strong>v${newVersion}</strong>!
                    </p>
                    <p class="text-gray-700 dark:text-gray-300">
                        To see the latest features and improvements, please reinstall the app:
                    </p>
                    <ol class="list-decimal list-inside space-y-2 text-gray-700 dark:text-gray-300 text-sm">
                        <li>Uninstall the current app from your device</li>
                        <li>Visit SweetMoney in your browser</li>
                        <li>Click "Install App" to reinstall with the new version</li>
                    </ol>
                    <div class="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                        <p class="text-xs text-blue-700 dark:text-blue-400">
                            💡 Your data is safe and will remain intact after reinstalling.
                        </p>
                    </div>
                </div>
            `;
            window.showModal(title, content);
        } else {
            // Fallback to alert
            alert(window.BASE_I18N.pwaNewVersionTitle + '\n\n' +
                  window.BASE_I18N.pwaInstalled + ' v' + oldVersion + '\n' +
                  window.BASE_I18N.pwaAvailable + ' v' + newVersion + '\n\n' +
                  window.BASE_I18N.pwaUpdateInstructions + '\n' +
                  window.BASE_I18N.pwaClickToDismiss);
        }
    }
}

// ===== 10. WEBSOCKET INITIALIZATION =====
function initializeWebSocket() {
    if (!window.IS_AUTHENTICATED) {
        console.log('[WebSocket] User not authenticated, skipping initialization');
        return;
    }

    // CRITICAL: Do NOT initialize WebSocket on configuration pages
    // Database restore operations need exclusive access to the DB file
    // WebSocket connections create locks that prevent file operations on Windows
    const currentPath = window.location.pathname;
    const isConfigPage = currentPath.includes('/configurations') || currentPath.includes('/settings');

    if (isConfigPage) {
        console.log('[WebSocket] Skipping initialization on configuration page to avoid DB locks');
        return;
    }

    // Store current user ID for comparison in RealtimeUI
    document.body.dataset.userId = window.USER_ID;

    // Create WebSocket manager instance (defined in websocket_manager.js)
    if (typeof WebSocketManager === 'undefined') {
        console.warn('[WebSocket] WebSocketManager not loaded');
        return;
    }

    const wsManager = new WebSocketManager();
    wsManager.connect();

    // Show connection status indicator (optional)
    wsManager.onConnectionStatus(function(status) {
        const indicator = document.getElementById('ws-status-indicator');
        if (indicator) {
            indicator.className = 'ws-' + status;
            indicator.title = 'WebSocket: ' + status;
        }
    });

    // Register message handlers for real-time updates
    wsManager.registerHandler('transaction_created', function(data) {
        if (typeof window.RealtimeUI !== 'undefined') {
            window.RealtimeUI.handleTransactionCreated(data);
        }
    });

    wsManager.registerHandler('transaction_updated', function(data) {
        if (typeof window.RealtimeUI !== 'undefined') {
            window.RealtimeUI.handleTransactionUpdated(data);
        }
    });

    wsManager.registerHandler('transaction_deleted', function(data) {
        if (typeof window.RealtimeUI !== 'undefined') {
            window.RealtimeUI.handleTransactionDeleted(data);
        }
    });

    wsManager.registerHandler('flowgroup_updated', function(data) {
        if (typeof window.RealtimeUI !== 'undefined') {
            window.RealtimeUI.handleFlowGroupUpdated(data);
        }
    });

    wsManager.registerHandler('balance_updated', function(data) {
        if (typeof window.RealtimeUI !== 'undefined') {
            window.RealtimeUI.handleBalanceUpdated(data);
        }
    });

    wsManager.registerHandler('notification', function(data) {
        // Trigger custom event for notifications.js to handle
        document.dispatchEvent(new CustomEvent('realtime:notification', {
            detail: { data: data }
        }));
    });
}

// ===== 11. UI COMPONENTS (Sidebar, Period Dropdown) - Phase 4 =====
function initializeUIComponents() {
    /**
     * UI Components Manager - Replaces Alpine.js
     * Handles sidebar toggle and period dropdown
     */
    class UIComponents {
        constructor() {
            this.sidebarOpen = false;
            this.periodDropdownOpen = false;
            this.init();
        }

        init() {
            // Sidebar toggle buttons
            document.querySelector('[data-action="open-sidebar"]')?.addEventListener('click', () => {
                this.openSidebar();
            });

            document.querySelector('[data-action="close-sidebar"]')?.addEventListener('click', () => {
                this.closeSidebar();
            });

            // Period dropdown
            const dropdownBtn = document.querySelector('[data-action="toggle-period-dropdown"]');
            if (dropdownBtn) {
                dropdownBtn.addEventListener('click', () => this.togglePeriodDropdown());

                // Click outside to close
                document.addEventListener('click', (e) => {
                    const container = e.target.closest('[data-dropdown-container="period"]');
                    if (!container && this.periodDropdownOpen) {
                        this.closePeriodDropdown();
                    }
                });
            }

            console.log('[UIComponents] Initialized (Phase 4)');
        }

        openSidebar() {
            this.sidebarOpen = true;
            const sidebar = document.getElementById('mobile-sidebar');
            if (sidebar) {
                sidebar.classList.remove('-translate-x-full');
                sidebar.classList.add('translate-x-0');
            }
        }

        closeSidebar() {
            this.sidebarOpen = false;
            const sidebar = document.getElementById('mobile-sidebar');
            if (sidebar) {
                sidebar.classList.remove('translate-x-0');
                sidebar.classList.add('-translate-x-full');
            }
        }

        togglePeriodDropdown() {
            this.periodDropdownOpen = !this.periodDropdownOpen;
            const dropdown = document.getElementById('period-dropdown-menu');
            if (dropdown) {
                dropdown.classList.toggle('hidden', !this.periodDropdownOpen);
            }
        }

        closePeriodDropdown() {
            this.periodDropdownOpen = false;
            const dropdown = document.getElementById('period-dropdown-menu');
            if (dropdown) {
                dropdown.classList.add('hidden');
            }
        }
    }

    // Initialize and expose globally
    window.uiComponents = new UIComponents();
}

// ===== UTILITY FUNCTIONS =====
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

console.log('[Base.js] Loaded successfully');
