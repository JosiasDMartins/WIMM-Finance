/**
 * Real-time UI Updates Handler
 * Handles WebSocket broadcast messages and updates the UI accordingly
 *
 * Security: Uses textContent (never innerHTML) to prevent XSS attacks
 * Compatibility: Works with all pages (dashboard, flowgroup, bank_reconciliation)
 */

(function() {
    'use strict';

    // Get current user ID from DOM
    const currentUserId = document.body.dataset.userId ? parseInt(document.body.dataset.userId) : null;

    // Locale settings for money formatting
    const decimalSeparator = window.decimalSeparator || ',';
    const thousandSeparator = window.thousandSeparator || '.';
    const currencySymbol = window.currencySymbol || 'R$';

    /**
     * Format currency value with locale settings
     */
    function formatCurrency(value) {
        if (value === null || value === undefined) return '';

        const num = parseFloat(value);
        if (isNaN(num)) return '';

        // Format with 2 decimal places
        const parts = Math.abs(num).toFixed(2).split('.');
        const integerPart = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, thousandSeparator);
        const formattedValue = integerPart + decimalSeparator + parts[1];

        return (num < 0 ? '-' : '') + currencySymbol + ' ' + formattedValue;
    }

    /**
     * Format date string to locale format
     */
    function formatDate(dateString) {
        if (!dateString) return '';

        try {
            const date = new Date(dateString);
            return date.toLocaleDateString();
        } catch (e) {
            return dateString;
        }
    }

    /**
     * Show toast notification for real-time updates
     */
    function showRealtimeToast(message, type, actor) {
        // Create toast container if doesn't exist
        let container = document.getElementById('realtime-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'realtime-toast-container';
            container.className = 'fixed top-4 right-4 z-50 space-y-2';
            container.style.maxWidth = '400px';
            document.body.appendChild(container);
        }

        // Create toast element
        const toast = document.createElement('div');
        toast.className = 'transform transition-all duration-300 translate-x-0 opacity-100';

        // Determine colors based on type
        let bgClass, borderClass, iconPath;
        switch(type) {
            case 'success':
                bgClass = 'bg-green-50 dark:bg-green-900/20';
                borderClass = 'border-green-200 dark:border-green-800';
                iconPath = 'M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z';
                break;
            case 'warning':
                bgClass = 'bg-yellow-50 dark:bg-yellow-900/20';
                borderClass = 'border-yellow-200 dark:border-yellow-800';
                iconPath = 'M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z';
                break;
            case 'error':
                bgClass = 'bg-red-50 dark:bg-red-900/20';
                borderClass = 'border-red-200 dark:border-red-800';
                iconPath = 'M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z';
                break;
            default: // 'info'
                bgClass = 'bg-blue-50 dark:bg-blue-900/20';
                borderClass = 'border-blue-200 dark:border-blue-800';
                iconPath = 'M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z';
        }

        toast.innerHTML = `
            <div class="flex items-start p-4 border rounded-lg shadow-lg ${bgClass} ${borderClass}">
                <svg class="h-5 w-5 text-gray-600 dark:text-gray-300 mt-0.5" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="${iconPath}" />
                </svg>
                <div class="ml-3 flex-1">
                    <p class="text-sm font-medium text-gray-900 dark:text-gray-100"></p>
                    ${actor ? `<p class="text-xs text-gray-500 dark:text-gray-400 mt-1"></p>` : ''}
                </div>
                <button class="ml-4 inline-flex text-gray-400 hover:text-gray-500 dark:hover:text-gray-300 focus:outline-none">
                    <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                    </svg>
                </button>
            </div>
        `;

        // Set message text (using textContent for security)
        toast.querySelector('p.text-sm').textContent = message;
        if (actor) {
            toast.querySelector('p.text-xs').textContent = actor.username;
        }

        // Close button handler
        toast.querySelector('button').addEventListener('click', function() {
            removeToast(toast);
        });

        // Add to container
        container.appendChild(toast);

        // Auto-remove after 5 seconds
        setTimeout(function() {
            removeToast(toast);
        }, 5000);
    }

    /**
     * Remove toast with animation
     */
    function removeToast(toast) {
        toast.classList.add('translate-x-full', 'opacity-0');
        setTimeout(function() {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }

    /**
     * Add highlight animation to element
     */
    function highlightElement(element, duration) {
        if (!element) return;

        duration = duration || 2000;
        element.classList.add('bg-yellow-100', 'dark:bg-yellow-900/30', 'transition-colors', 'duration-500');

        setTimeout(function() {
            element.classList.remove('bg-yellow-100', 'dark:bg-yellow-900/30');
            setTimeout(function() {
                element.classList.remove('transition-colors', 'duration-500');
            }, 500);
        }, duration);
    }

    /**
     * Trigger custom event for other scripts to listen to
     */
    function triggerCustomEvent(eventName, detail) {
        const event = new CustomEvent(eventName, { detail: detail, bubbles: true });
        document.dispatchEvent(event);
    }

    // ==============================================
    // TRANSACTION HANDLERS
    // ==============================================

    window.RealtimeUI = window.RealtimeUI || {};

    window.RealtimeUI.handleTransactionCreated = function(data) {
        console.log('[RealtimeUI] Transaction created:', data);

        // Trigger custom event for page-specific handlers
        triggerCustomEvent('realtime:transaction:created', data);

        // Try to update dashboard if present
        if (typeof window.DashboardRealtime !== 'undefined' && window.DashboardRealtime.addTransaction) {
            window.DashboardRealtime.addTransaction(data.data);
        }

        // Try to update flowgroup page if present
        if (typeof window.FlowGroupRealtime !== 'undefined' && window.FlowGroupRealtime.addTransaction) {
            window.FlowGroupRealtime.addTransaction(data.data);
        }
    };

    window.RealtimeUI.handleTransactionUpdated = function(data) {
        console.log('[RealtimeUI] Transaction updated:', data);

        // Trigger custom event
        triggerCustomEvent('realtime:transaction:updated', data);

        // Find and update transaction row
        const row = document.querySelector(`tr[data-transaction-id="${data.data.id}"]`);
        if (row) {
            // Update description
            const descCell = row.querySelector('[data-field="description"]');
            if (descCell) descCell.textContent = data.data.description;

            // Update amount
            const amountCell = row.querySelector('[data-field="amount"]');
            if (amountCell) amountCell.textContent = formatCurrency(data.data.amount);

            // Update date
            const dateCell = row.querySelector('[data-field="date"]');
            if (dateCell) dateCell.textContent = formatDate(data.data.date);

            // Update member
            const memberCell = row.querySelector('[data-field="member"]');
            if (memberCell && data.data.member) memberCell.textContent = data.data.member;

            // Highlight update
            highlightElement(row);
        }

        // Try page-specific handlers
        if (typeof window.DashboardRealtime !== 'undefined' && window.DashboardRealtime.updateTransaction) {
            window.DashboardRealtime.updateTransaction(data.data);
        }

        // Try FlowGroup page handler
        console.log('[RealtimeUI] Checking for FlowGroup handler...', typeof window.FlowGroupRealtime);
        if (typeof window.FlowGroupRealtime !== 'undefined' && window.FlowGroupRealtime.updateTransaction) {
            console.log('[RealtimeUI] Calling FlowGroupRealtime.updateTransaction()');
            window.FlowGroupRealtime.updateTransaction(data.data);
        } else {
            console.log('[RealtimeUI] FlowGroupRealtime not available');
        }
    };

    window.RealtimeUI.handleTransactionDeleted = function(data) {
        console.log('[RealtimeUI] Transaction deleted:', data);

        // Trigger custom event
        triggerCustomEvent('realtime:transaction:deleted', data);

        // Find and remove transaction row with animation
        const row = document.querySelector(`tr[data-transaction-id="${data.data.id}"]`);
        if (row) {
            row.classList.add('opacity-0', 'transition-opacity', 'duration-300');
            setTimeout(function() {
                if (row.parentNode) {
                    row.parentNode.removeChild(row);
                }
            }, 300);
        }

        // Try page-specific handlers
        if (typeof window.DashboardRealtime !== 'undefined' && window.DashboardRealtime.removeTransaction) {
            window.DashboardRealtime.removeTransaction(data.data.id);
        }

        // Try FlowGroup page handler
        if (typeof window.FlowGroupRealtime !== 'undefined' && window.FlowGroupRealtime.removeTransaction) {
            window.FlowGroupRealtime.removeTransaction(data.data.id);
        }
    };

    // ==============================================
    // FLOWGROUP HANDLERS
    // ==============================================

    window.RealtimeUI.handleFlowGroupCreated = function(data) {
        console.log('[RealtimeUI] FlowGroup created:', data);

        // Trigger custom event
        triggerCustomEvent('realtime:flowgroup:created', data);

        // Try page-specific handler (dashboard)
        if (typeof window.DashboardRealtime !== 'undefined' && window.DashboardRealtime.addFlowGroup) {
            window.DashboardRealtime.addFlowGroup(data.data);
        }
    };

    window.RealtimeUI.handleFlowGroupUpdated = function(data) {
        console.log('[RealtimeUI] FlowGroup updated:', data);

        // Trigger custom event
        triggerCustomEvent('realtime:flowgroup:updated', data);

        // Try page-specific handler (dashboard)
        if (typeof window.DashboardRealtime !== 'undefined' && window.DashboardRealtime.updateFlowGroup) {
            window.DashboardRealtime.updateFlowGroup(data.data);
        }

        // Try page-specific handler (flowgroup edit page)
        if (typeof window.FlowGroupRealtime !== 'undefined' && window.FlowGroupRealtime.updateFlowGroup) {
            window.FlowGroupRealtime.updateFlowGroup(data.data);
        }
    };

    window.RealtimeUI.handleFlowGroupDeleted = function(data) {
        console.log('[RealtimeUI] FlowGroup deleted:', data);

        // Trigger custom event
        triggerCustomEvent('realtime:flowgroup:deleted', data);

        // Try page-specific handler (dashboard)
        if (typeof window.DashboardRealtime !== 'undefined' && window.DashboardRealtime.removeFlowGroup) {
            window.DashboardRealtime.removeFlowGroup(data.data.id);
        }
    };

    window.RealtimeUI.handleFlowGroupReordered = function(data) {
        console.log('[RealtimeUI] FlowGroup reordered:', data);

        // Trigger custom event
        triggerCustomEvent('realtime:flowgroup:reordered', data);

        // Try page-specific handler (dashboard)
        if (typeof window.DashboardRealtime !== 'undefined' && window.DashboardRealtime.reorderFlowGroups) {
            window.DashboardRealtime.reorderFlowGroups(data.data.groups);
        }
    };

    // ==============================================
    // BALANCE HANDLERS
    // ==============================================

    window.RealtimeUI.handleBalanceUpdated = function(data) {
        console.log('[RealtimeUI] Balance updated (generic):', data);

        // Trigger custom event for dashboard and other pages to listen
        triggerCustomEvent('realtime:balance:updated', data);
    };

    // ==============================================
    // BANK BALANCE HANDLERS
    // ==============================================

    window.RealtimeUI.handleBankBalanceUpdated = function(data) {
        console.log('[RealtimeUI] Bank balance updated:', data);

        // Trigger custom event
        triggerCustomEvent('realtime:bankbalance:updated', data);

        // Find and update bank balance element
        const element = document.querySelector(`[data-bankbalance-id="${data.data.id}"]`);
        if (element) {
            // Update bank name
            const nameEl = element.querySelector('[data-field="bank_name"]');
            if (nameEl) nameEl.textContent = data.data.bank_name;

            // Update balance
            const balanceEl = element.querySelector('[data-field="balance"]');
            if (balanceEl) balanceEl.textContent = formatCurrency(data.data.balance);

            // Highlight update
            highlightElement(element);
        }

        // Try page-specific handler
        if (typeof window.BankReconciliationRealtime !== 'undefined' && window.BankReconciliationRealtime.updateBalance) {
            window.BankReconciliationRealtime.updateBalance(data.data);
        }
    };

    window.RealtimeUI.handleBankBalanceDeleted = function(data) {
        console.log('[RealtimeUI] Bank balance deleted:', data);

        // Trigger custom event
        triggerCustomEvent('realtime:bankbalance:deleted', data);

        // Find and remove bank balance row with animation
        const element = document.querySelector(`[data-bankbalance-id="${data.data.id}"]`);
        if (element) {
            element.classList.add('opacity-0', 'transition-opacity', 'duration-300');
            setTimeout(function() {
                if (element.parentNode) {
                    element.parentNode.removeChild(element);
                }
            }, 300);
        }
    };

    // ==============================================
    // RECONCILIATION MODE HANDLER
    // ==============================================

    window.RealtimeUI.handleReconciliationModeChanged = function(data) {
        console.log('[RealtimeUI] Reconciliation mode changed:', data);

        // Trigger custom event
        triggerCustomEvent('realtime:reconciliation:mode_changed', data);

        // Try BankReconciliationRealtime handler
        if (typeof window.BankReconciliationRealtime !== 'undefined' && window.BankReconciliationRealtime.handleModeChange) {
            window.BankReconciliationRealtime.handleModeChange(data.data);
        }
    };

    // ==============================================
    // CONFIGURATION HANDLER
    // ==============================================

    window.RealtimeUI.handleConfigurationUpdated = function(data) {
        console.log('[RealtimeUI] Configuration updated:', data);

        // Trigger custom event
        triggerCustomEvent('realtime:configuration:updated', data);

        // Try ConfigurationRealtime handler
        if (typeof window.ConfigurationRealtime !== 'undefined' && window.ConfigurationRealtime.updateConfiguration) {
            window.ConfigurationRealtime.updateConfiguration(data.data);
        }
    };

    // ==============================================
    // MEMBER HANDLERS
    // ==============================================

    window.RealtimeUI.handleMemberAdded = function(data) {
        console.log('[RealtimeUI] Member added:', data);

        // Trigger custom event
        triggerCustomEvent('realtime:member:added', data);

        // Try MembersRealtime handler
        if (typeof window.MembersRealtime !== 'undefined' && window.MembersRealtime.addMember) {
            window.MembersRealtime.addMember(data.data);
        }
    };

    window.RealtimeUI.handleMemberUpdated = function(data) {
        console.log('[RealtimeUI] Member updated:', data);

        // Trigger custom event
        triggerCustomEvent('realtime:member:updated', data);

        // Try MembersRealtime handler
        if (typeof window.MembersRealtime !== 'undefined' && window.MembersRealtime.updateMember) {
            window.MembersRealtime.updateMember(data.data);
        }
    };

    window.RealtimeUI.handleMemberRemoved = function(data) {
        console.log('[RealtimeUI] Member removed:', data);

        // Trigger custom event
        triggerCustomEvent('realtime:member:removed', data);

        // Try MembersRealtime handler
        if (typeof window.MembersRealtime !== 'undefined' && window.MembersRealtime.removeMember) {
            window.MembersRealtime.removeMember(data.data);
        }
    };

    // ==============================================
    // NOTIFICATION HANDLER
    // ==============================================

    window.RealtimeUI.handleNotification = function(data) {
        console.log('[RealtimeUI] Notification received:', data);

        // Trigger custom event for notification system to handle
        triggerCustomEvent('realtime:notification', data);
    };

    // Export utilities for external use
    window.RealtimeUI.utils = {
        formatCurrency: formatCurrency,
        formatDate: formatDate,
        showToast: showRealtimeToast,
        highlightElement: highlightElement
    };

    console.log('[RealtimeUI] Loaded successfully');

})();
