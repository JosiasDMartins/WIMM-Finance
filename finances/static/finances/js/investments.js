// ============================================
// INVESTMENTS.JS - PHASE 3 CSP COMPLIANCE
// ============================================
// Investments Real-time Updates
// Version: 20251231-001
// Extracted from: invest.html

(function() {
    'use strict';

    // Investments Real-time Updates
    window.InvestmentsRealtime = {
        /**
         * Update investment balance display
         */
        updateBalance: function() {
            console.log('[InvestmentsRT] Updating investment balance...');

            const urlParams = new URLSearchParams(window.location.search);
            const period = urlParams.get('period') || '';
            const url = document.getElementById('investments-config')?.dataset.ajaxUrl || '/get-investment-balance-ajax/';
            const fullUrl = url + (period ? `?period=${period}` : '');

            fetch(fullUrl, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    const balanceElement = document.querySelector('.text-4xl.font-bold');
                    if (balanceElement && window.RealtimeUI && window.RealtimeUI.utils) {
                        // Format the balance with currency symbol and separators
                        const formattedBalance = window.RealtimeUI.utils.formatCurrency(data.available_balance);
                        balanceElement.textContent = formattedBalance;
                        console.log('[InvestmentsRT] Balance updated to:', formattedBalance);
                    }
                } else {
                    console.error('[InvestmentsRT] Error updating balance:', data.error);
                }
            })
            .catch(error => {
                console.error('[InvestmentsRT] Fetch error:', error);
            });
        },

        /**
         * Handle transaction events - check if it's an investment transaction
         */
        handleTransactionEvent: function(transactionData) {
            // Check if the transaction belongs to an investment FlowGroup
            if (transactionData.is_investment) {
                console.log('[InvestmentsRT] Investment transaction event detected:', transactionData);
                this.updateBalance();
            }
        },

        /**
         * Handle FlowGroup update - check if is_investment flag changed
         */
        handleFlowGroupUpdate: function(flowgroupData) {
            // If a FlowGroup's is_investment flag changed, update balance
            if (flowgroupData.hasOwnProperty('is_investment')) {
                console.log('[InvestmentsRT] FlowGroup investment status changed:', flowgroupData);
                this.updateBalance();
            }
        }
    };

    // Listen for transaction events
    document.addEventListener('realtime:transaction:created', function(event) {
        if (window.InvestmentsRealtime && window.InvestmentsRealtime.handleTransactionEvent) {
            window.InvestmentsRealtime.handleTransactionEvent(event.detail.data);
        }
    });

    document.addEventListener('realtime:transaction:updated', function(event) {
        if (window.InvestmentsRealtime && window.InvestmentsRealtime.handleTransactionEvent) {
            window.InvestmentsRealtime.handleTransactionEvent(event.detail.data);
        }
    });

    document.addEventListener('realtime:transaction:deleted', function(event) {
        if (window.InvestmentsRealtime && window.InvestmentsRealtime.handleTransactionEvent) {
            window.InvestmentsRealtime.handleTransactionEvent(event.detail.data);
        }
    });

    // Listen for FlowGroup events (when is_investment changes)
    document.addEventListener('realtime:flowgroup:updated', function(event) {
        if (window.InvestmentsRealtime && window.InvestmentsRealtime.handleFlowGroupUpdate) {
            window.InvestmentsRealtime.handleFlowGroupUpdate(event.detail.data);
        }
    });

    console.log('[InvestmentsRealtime] Loaded successfully');
})();
