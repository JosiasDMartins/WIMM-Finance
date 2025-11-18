// finances/static/finances/js/notifications.js

(function() {
    'use strict';
    
    // Configurações
    const POLL_INTERVAL = 10000; // 30 segundos
    
    // State
    let isDropdownOpen = false;// finances/static/finances/js/notifications.js

(function() {
    'use strict';
    
    // Configurações
    const POLL_INTERVAL = 30000; // 30 segundos
    
    // State
    let isDropdownOpen = false;
    let pollTimer = null;
    let lastNotificationCount = 0;
    
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
    
    const csrftoken = getCookie('csrftoken');
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
        console.log('[NOTIF JS] ========================================');
        console.log('[NOTIF JS] Loading notifications...');
        
        fetch('/api/notifications/')
            .then(response => {
                console.log('[NOTIF JS] API response status:', response.status);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('[NOTIF JS] API response data:', data);
                console.log('[NOTIF JS] Success:', data.success);
                console.log('[NOTIF JS] Count:', data.count);
                
                if (data.success) {
                    console.log('[NOTIF JS] Notifications received:', data.notifications.length);
                    
                    // Log por tipo
                    const typeCount = {};
                    data.notifications.forEach(n => {
                        typeCount[n.type] = (typeCount[n.type] || 0) + 1;
                        console.log('[NOTIF JS]   -', n.type, ':', n.message);
                    });
                    console.log('[NOTIF JS] By type:', typeCount);
                    
                    renderNotifications(data.notifications);
                    updateBadge(data.count);
                } else {
                    console.error('[NOTIF JS] API returned success=false:', data.error);
                    notificationList.innerHTML = '<div class="px-4 py-3 text-sm text-red-600 dark:text-red-400">Error: ' + data.error + '</div>';
                }
                console.log('[NOTIF JS] ========================================');
            })
            .catch(error => {
                console.error('[NOTIF JS] Error loading notifications:', error);
                notificationList.innerHTML = '<div class="px-4 py-3 text-sm text-red-600 dark:text-red-400">Error loading notifications: ' + error.message + '</div>';
            });
    }
    
    // Update badge count only (for polling)
    function updateBadgeOnly() {
        if (isDropdownOpen) {
            console.log('[NOTIF JS] Skipping badge update (dropdown is open)');
            return;
        }
        
        console.log('[NOTIF JS] Polling: Updating badge...');
        
        fetch('/api/notifications/')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    console.log('[NOTIF JS] Polling: Badge update - count:', data.count);
                    
                    // Detecta nova notificação
                    if (data.count > lastNotificationCount) {
                        console.log('[NOTIF JS] NEW NOTIFICATION DETECTED!');
                        console.log('[NOTIF JS] Previous count:', lastNotificationCount, '→ New count:', data.count);
                    }
                    
                    lastNotificationCount = data.count;
                    updateBadge(data.count);
                }
            })
            .catch(error => console.error('[NOTIF JS] Error updating badge:', error));
    }
    
    // Render notifications list
    function renderNotifications(notifications) {
        console.log('[NOTIF JS] Rendering', notifications.length, 'notifications');
        
        if (notifications.length === 0) {
            notificationList.innerHTML = '<div class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 text-center">No notifications</div>';
            return;
        }
        
        let html = '';
        notifications.forEach(notif => {
            const iconClass = getNotificationIcon(notif.type);
            const colorClass = getNotificationColor(notif.type);
            
            console.log('[NOTIF JS] Rendering notification:', notif.id, notif.type, notif.message);
            
            html += `
                <div class="notification-item border-b border-gray-100 dark:border-gray-700" data-notification-id="${notif.id}">
                    <a href="${escapeHtml(notif.target_url)}" 
                       class="block px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                       onclick="acknowledgeAndNavigate(event, ${notif.id}, '${escapeHtml(notif.target_url)}')">
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
        console.log('[NOTIF JS] Notifications rendered successfully');
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
        console.log('[NOTIF JS] Updating badge with count:', count);
        
        if (count > 0) {
            notificationBadge.textContent = count > 99 ? '99+' : count;
            notificationBadge.classList.remove('hidden');
            console.log('[NOTIF JS] Badge shown with count:', notificationBadge.textContent);
        } else {
            notificationBadge.classList.add('hidden');
            console.log('[NOTIF JS] Badge hidden');
        }
    }
    
    // Escape HTML to prevent XSS
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Acknowledge notification and navigate
    window.acknowledgeAndNavigate = function(event, notificationId, targetUrl) {
        event.preventDefault();
        
        console.log('[NOTIF JS] Acknowledging notification:', notificationId);
        
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
            console.log('[NOTIF JS] Acknowledge response:', data);
            
            if (data.success) {
                // Remove notification from list
                const notifElement = document.querySelector(`.notification-item[data-notification-id="${notificationId}"]`);
                if (notifElement) {
                    notifElement.remove();
                }
                
                // Update badge
                updateBadge(data.remaining_count);
                lastNotificationCount = data.remaining_count;
                
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
    };
    
    // Acknowledge all notifications
    function acknowledgeAllNotifications(e) {
        e.preventDefault();
        
        console.log('[NOTIF JS] Acknowledging all notifications...');
        
        fetch('/api/notifications/acknowledge-all/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken
            }
        })
        .then(response => response.json())
        .then(data => {
            console.log('[NOTIF JS] Acknowledge all response:', data);
            
            if (data.success) {
                updateBadge(0);
                lastNotificationCount = 0;
                notificationList.innerHTML = '<div class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 text-center">No notifications</div>';
            }
        })
        .catch(error => {
            console.error('[NOTIF JS] Error acknowledging all notifications:', error);
        });
    }
    
    // Start polling for new notifications
    function startPolling() {
        console.log('[NOTIF JS] Starting polling (interval:', POLL_INTERVAL / 1000, 'seconds)');
        
        // Initial update
        updateBadgeOnly();
        
        // Set interval
        pollTimer = setInterval(updateBadgeOnly, POLL_INTERVAL);
    }
    
    // Stop polling (for cleanup if needed)
    function stopPolling() {
        if (pollTimer) {
            console.log('[NOTIF JS] Stopping polling');
            clearInterval(pollTimer);
            pollTimer = null;
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
        
        // Start polling
        startPolling();
        
        // Expose stop function for debugging
        window.stopNotificationPolling = stopPolling;
        window.forceNotificationLoad = loadNotifications;
        
        console.log('[NOTIF JS] Notification system initialized successfully');
        console.log('[NOTIF JS] ========================================');
    }
    
    // Wait for DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
    let pollTimer = null;
    
    // Elements
    const notificationBell = document.getElementById('notification-bell');
    const notificationDropdown = document.getElementById('notification-dropdown');
    const notificationBadge = document.getElementById('notification-badge');
    const notificationList = document.getElementById('notification-list');
    const acknowledgeAllBtn = document.getElementById('acknowledge-all-btn');
    
    console.log('[NOTIF JS] Notification system initializing...');
    console.log('[NOTIF JS] Elements found:', {
        bell: !!notificationBell,
        dropdown: !!notificationDropdown,
        badge: !!notificationBadge,
        list: !!notificationList,
        ackAll: !!acknowledgeAllBtn
    });
    
    // Utility: Get CSRF token from cookies
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
    
    const csrftoken = getCookie('csrftoken');
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
        console.log('[NOTIF JS] Loading notifications...');
        
        fetch('/api/notifications/')
            .then(response => {
                console.log('[NOTIF JS] API response status:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('[NOTIF JS] API response data:', data);
                
                if (data.success) {
                    console.log('[NOTIF JS] Notifications count:', data.count);
                    console.log('[NOTIF JS] Notifications:', data.notifications);
                    renderNotifications(data.notifications);
                    updateBadge(data.count);
                } else {
                    console.error('[NOTIF JS] API returned success=false:', data.error);
                }
            })
            .catch(error => {
                console.error('[NOTIF JS] Error loading notifications:', error);
                notificationList.innerHTML = '<div class="px-4 py-3 text-sm text-red-600 dark:text-red-400">Error loading notifications</div>';
            });
    }
    
    // Update badge count only (for polling)
    function updateBadgeOnly() {
        if (isDropdownOpen) {
            console.log('[NOTIF JS] Skipping badge update (dropdown is open)');
            return;
        }
        
        console.log('[NOTIF JS] Updating badge...');
        
        fetch('/api/notifications/')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('[NOTIF JS] Badge update - count:', data.count);
                    updateBadge(data.count);
                }
            })
            .catch(error => console.error('[NOTIF JS] Error updating badge:', error));
    }
    
    // Render notifications list
    function renderNotifications(notifications) {
        console.log('[NOTIF JS] Rendering', notifications.length, 'notifications');
        
        if (notifications.length === 0) {
            notificationList.innerHTML = '<div class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 text-center">No notifications</div>';
            return;
        }
        
        let html = '';
        notifications.forEach(notif => {
            const iconClass = getNotificationIcon(notif.type);
            const colorClass = getNotificationColor(notif.type);
            
            console.log('[NOTIF JS] Rendering notification:', notif.id, notif.message);
            
            html += `
                <div class="notification-item border-b border-gray-100 dark:border-gray-700" data-notification-id="${notif.id}">
                    <a href="${escapeHtml(notif.target_url)}" 
                       class="block px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                       onclick="acknowledgeAndNavigate(event, ${notif.id}, '${escapeHtml(notif.target_url)}')">
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
        console.log('[NOTIF JS] Notifications rendered successfully');
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
        console.log('[NOTIF JS] Updating badge with count:', count);
        
        if (count > 0) {
            notificationBadge.textContent = count > 99 ? '99+' : count;
            notificationBadge.classList.remove('hidden');
            console.log('[NOTIF JS] Badge shown with count:', notificationBadge.textContent);
        } else {
            notificationBadge.classList.add('hidden');
            console.log('[NOTIF JS] Badge hidden');
        }
    }
    
    // Escape HTML to prevent XSS
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Acknowledge notification and navigate
    window.acknowledgeAndNavigate = function(event, notificationId, targetUrl) {
        event.preventDefault();
        
        console.log('[NOTIF JS] Acknowledging notification:', notificationId);
        
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
            console.log('[NOTIF JS] Acknowledge response:', data);
            
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
    };
    
    // Acknowledge all notifications
    function acknowledgeAllNotifications(e) {
        e.preventDefault();
        
        console.log('[NOTIF JS] Acknowledging all notifications...');
        
        fetch('/api/notifications/acknowledge-all/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken
            }
        })
        .then(response => response.json())
        .then(data => {
            console.log('[NOTIF JS] Acknowledge all response:', data);
            
            if (data.success) {
                updateBadge(0);
                notificationList.innerHTML = '<div class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 text-center">No notifications</div>';
            }
        })
        .catch(error => {
            console.error('[NOTIF JS] Error acknowledging all notifications:', error);
        });
    }
    
    // Start polling for new notifications
    function startPolling() {
        console.log('[NOTIF JS] Starting polling (interval:', POLL_INTERVAL / 1000, 'seconds)');
        
        // Initial update
        updateBadgeOnly();
        
        // Set interval
        pollTimer = setInterval(updateBadgeOnly, POLL_INTERVAL);
    }
    
    // Stop polling (for cleanup if needed)
    function stopPolling() {
        if (pollTimer) {
            console.log('[NOTIF JS] Stopping polling');
            clearInterval(pollTimer);
            pollTimer = null;
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
        
        // Start polling
        startPolling();
        
        // Expose stop function for debugging
        window.stopNotificationPolling = stopPolling;
        
        console.log('[NOTIF JS] Notification system initialized successfully');
    }
    
    // Wait for DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();