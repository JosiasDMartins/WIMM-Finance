// finances/static/finances/js/notifications.js
// Version: 20251231-001 - Using utils.js for common functions

(function() {
    'use strict';

    // Configurações
    const POLL_INTERVAL = 30000; // 30 segundos

    // State
    let isDropdownOpen = false;
    let pollTimer = null;

    // Elements
    const notificationBell = document.getElementById('notification-bell');
    const notificationDropdown = document.getElementById('notification-dropdown');
    const notificationBadge = document.getElementById('notification-badge');
    const notificationList = document.getElementById('notification-list');
    const acknowledgeAllBtn = document.getElementById('acknowledge-all-btn');

    console.log('[NOTIF JS] ========================================');
    console.log('[NOTIF JS] Notification system initializing...');
    console.log('[NOTIF JS] Elements found:', {
        bell: !!notificationBell,
        dropdown: !!notificationDropdown,
        badge: !!notificationBadge,
        list: !!notificationList,
        ackAll: !!acknowledgeAllBtn
    });

    // Utility: Get CSRF token from cookies
    // getCookie - using utils.js (window.getCookie)

    const csrftoken = window.getCookie('csrftoken');
    console.log('[NOTIF JS] CSRF token:', csrftoken ? 'Found' : 'NOT FOUND');

    // Toggle dropdown
    function toggleDropdown(e) {
        e.preventDefault();
        e.stopPropagation();

        console.log('[NOTIF JS] Toggle dropdown clicked');

        if (isDropdownOpen) {
            closeDropdown();
        } else {
            openDropdown();
        }
    }

    function openDropdown() {
        console.log('[NOTIF JS] Opening dropdown...');
        loadNotifications();
        notificationDropdown.classList.remove('hidden');
        isDropdownOpen = true;
    }

    function closeDropdown() {
        console.log('[NOTIF JS] Closing dropdown...');
        notificationDropdown.classList.add('hidden');
        isDropdownOpen = false;
    }

    // Close dropdown when clicking outside
    function handleClickOutside(e) {
        if (isDropdownOpen &&
            !notificationDropdown.contains(e.target) &&
            !notificationBell.contains(e.target)) {
            closeDropdown();
        }
    }

    // Load notifications from API
    function loadNotifications() {
        fetch('/api/notifications/')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    renderNotifications(data.notifications);
                    updateBadge(data.count);
                } else {
                    console.error('[NOTIF JS] API returned success=false:', data.error);
                    notificationList.innerHTML = '<div class="px-4 py-3 text-sm text-red-600 dark:text-red-400">Error: ' + data.error + '</div>';
                }
            })
            .catch(error => {
                console.error('[NOTIF JS] Error loading notifications:', error);
                notificationList.innerHTML = '<div class="px-4 py-3 text-sm text-red-600 dark:text-red-400">Error loading notifications: ' + error.message + '</div>';
            });
    }

    // Update badge count only (for polling)
    function updateBadgeOnly() {
        if (isDropdownOpen) {
            return;
        }

        fetch('/api/notifications/')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    updateBadge(data.count);
                }
            })
            .catch(error => console.error('[NOTIF JS] Error updating badge:', error));
    }

    // Render notifications list
    function renderNotifications(notifications) {
        if (notifications.length === 0) {
            notificationList.innerHTML = '<div class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 text-center">No notifications</div>';
            return;
        }

        let html = '';
        notifications.forEach(notif => {
            const iconClass = getNotificationIcon(notif.type);
            const colorClass = getNotificationColor(notif.type);

            html += `
                <div class="notification-item border-b border-gray-100 dark:border-gray-700" data-notification-id="${notif.id}" data-target-url="${escapeHtml(notif.target_url)}">
                    <a href="${escapeHtml(notif.target_url)}"
                       class="notification-link block px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
                        <div class="flex items-start">
                            <span class="material-symbols-outlined ${colorClass} mr-3 mt-0.5 flex-shrink-0">${iconClass}</span>
                            <div class="flex-1 min-w-0">
                                <p class="text-sm text-gray-800 dark:text-gray-200">${escapeHtml(notif.message)}</p>
                                <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">${notif.created_at}</p>
                            </div>
                        </div>
                    </a>
                </div>
            `;
        });

        notificationList.innerHTML = html;

        // Add event delegation for notification clicks
        attachNotificationClickHandlers();
    }

    // Attach click handlers using event delegation (CSP-safe)
    function attachNotificationClickHandlers() {
        // Remove old listeners if any
        const links = notificationList.querySelectorAll('.notification-link');
        links.forEach(link => {
            link.addEventListener('click', handleNotificationClick);
        });
    }

    // Handle notification click
    function handleNotificationClick(event) {
        event.preventDefault();

        const notificationItem = event.currentTarget.closest('.notification-item');
        const notificationId = notificationItem.dataset.notificationId;
        const targetUrl = notificationItem.dataset.targetUrl;

        acknowledgeAndNavigate(notificationId, targetUrl);
    }

    // Get icon based on notification type
    function getNotificationIcon(type) {
        switch(type) {
            case 'OVERDUE':
                return 'schedule';
            case 'OVERBUDGET':
                return 'warning';
            case 'NEW_TRANSACTION':
                return 'receipt';
            default:
                return 'notifications';
        }
    }

    // Get color based on notification type
    function getNotificationColor(type) {
        switch(type) {
            case 'OVERDUE':
                return 'text-red-500';
            case 'OVERBUDGET':
                return 'text-orange-500';
            case 'NEW_TRANSACTION':
                return 'text-blue-500';
            default:
                return 'text-gray-500';
        }
    }

    // Update badge count
    function updateBadge(count) {
        if (count > 0) {
            notificationBadge.textContent = count > 99 ? '99+' : count;
            notificationBadge.classList.remove('hidden');
        } else {
            notificationBadge.classList.add('hidden');
        }
    }

    // Escape HTML to prevent XSS
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Acknowledge notification and navigate
    function acknowledgeAndNavigate(notificationId, targetUrl) {
        const formData = new FormData();
        formData.append('notification_id', notificationId);

        fetch('/api/notifications/acknowledge/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken
            },
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Remove notification from list
                const notifElement = document.querySelector(`.notification-item[data-notification-id="${notificationId}"]`);
                if (notifElement) {
                    notifElement.remove();
                }

                // Update badge
                updateBadge(data.remaining_count);

                // Check if list is now empty
                const remainingItems = document.querySelectorAll('.notification-item');
                if (remainingItems.length === 0) {
                    notificationList.innerHTML = '<div class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 text-center">No notifications</div>';
                }

                // Navigate to target URL
                window.location.href = targetUrl;
            }
        })
        .catch(error => {
            console.error('[NOTIF JS] Error acknowledging notification:', error);
            // Navigate anyway
            window.location.href = targetUrl;
        });
    }

    // Acknowledge all notifications
    function acknowledgeAllNotifications(e) {
        e.preventDefault();

        fetch('/api/notifications/acknowledge-all/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateBadge(0);
                notificationList.innerHTML = '<div class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 text-center">No notifications</div>';
            }
        })
        .catch(error => {
            console.error('[NOTIF JS] Error acknowledging all notifications:', error);
        });
    }

    // Start polling for new notifications (DEPRECATED - now using WebSocket)
    function startPolling() {
        // Polling is no longer used - WebSocket handles real-time notification updates
        // Initial badge update only
        updateBadgeOnly();
    }

    // Stop polling (for cleanup if needed)
    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    // Handle notification received via WebSocket
    function handleWebSocketNotification(data) {
        // Reload badge count from server to ensure accuracy
        updateBadgeOnly();

        // If dropdown is open, reload notifications list
        if (isDropdownOpen) {
            loadNotifications();
        }
    }

    // Initialize
    function init() {
        if (!notificationBell) {
            console.warn('[NOTIF JS] Notification bell element not found - aborting initialization');
            return;
        }

        // Event listeners
        notificationBell.addEventListener('click', toggleDropdown);
        document.addEventListener('click', handleClickOutside);

        if (acknowledgeAllBtn) {
            acknowledgeAllBtn.addEventListener('click', acknowledgeAllNotifications);
        }

        // Start polling (only does initial badge update now)
        startPolling();

        // Listen for WebSocket notifications
        document.addEventListener('realtime:notification', function(event) {
            handleWebSocketNotification(event.detail.data);
        });

        // Expose functions for debugging
        window.stopNotificationPolling = stopPolling;
        window.forceNotificationLoad = loadNotifications;
        window.handleWebSocketNotification = handleWebSocketNotification;

        console.log('[NOTIF JS] Notification system initialized successfully (WebSocket mode)');
        console.log('[NOTIF JS] ========================================');
    }

    // Wait for DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
