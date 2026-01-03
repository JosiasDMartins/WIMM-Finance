/**
 * Bank Reconciliation JavaScript
 * External JavaScript file (CSP compliant - no inline scripts)
 * Handles: Money mask, CRUD operations, real-time updates
 * Version: 20251231-001 - Using utils.js for common functions
 */

// Wait for DOM to be ready
document.addEventListener('DOMContentLoaded', function() {
    'use strict';
    initBankReconciliation();
});

function initBankReconciliation() {
    // Read configuration from data attributes
    const config = document.getElementById('bank-recon-config');
    if (!config) {
        console.error('[BankReconciliation] Configuration element not found!');
        return;
    }

    // Extract configuration
    window.BANK_RECON_CONFIG = {
        decimalSeparator: config.dataset.decimalSeparator,
        thousandSeparator: config.dataset.thousandSeparator,
        currencySymbol: config.dataset.currencySymbol,
        startDate: config.dataset.startDate,
        discrepancyPercentageTolerance: config.dataset.discrepancyPercentageTolerance,
        urls: {
            saveBankBalance: config.dataset.urlSaveBankBalance,
            deleteBankBalance: config.dataset.urlDeleteBankBalance,
            getReconciliationSummary: config.dataset.urlGetReconciliationSummary,
            toggleReconciliationMode: config.dataset.urlToggleReconciliationMode
        },
        i18n: {
            pleaseEnterDescription: config.dataset.i18nPleaseEnterDescription,
            errorSavingBalance: config.dataset.i18nErrorSavingBalance,
            networkErrorOccurred: config.dataset.i18nNetworkErrorOccurred,
            deleteConfirm: config.dataset.i18nDeleteConfirm,
            errorDeletingBalance: config.dataset.i18nErrorDeletingBalance,
            warningDiscrepancyDetected: config.dataset.i18nWarningDiscrepancyDetected,
            warningDiscrepancyMessage: config.dataset.i18nWarningDiscrepancyMessage,
            reconciliationOk: config.dataset.i18nReconciliationOk,
            reconciliationOkMessage: config.dataset.i18nReconciliationOkMessage,
            discrepancyExceedsMember: config.dataset.i18nDiscrepancyExceedsMember
        },
        csrfToken: getCookie('csrftoken')
    };

    // Shortcuts
    window.decimalSeparator = window.BANK_RECON_CONFIG.decimalSeparator;
    window.thousandSeparator = window.BANK_RECON_CONFIG.thousandSeparator;
    window.currencySymbol = window.BANK_RECON_CONFIG.currencySymbol;
    window.csrftoken = window.BANK_RECON_CONFIG.csrfToken;

    console.log('[BankReconciliation] Configuration loaded');

    // Initialize money mask
    initMoneyMask();

    // Initialize real-time listeners
    initRealtimeListeners();
}

// ===== UTILITY FUNCTIONS =====

// getCookie, applyMoneyMask, getRawValue, formatCurrency - using utils.js

function initMoneyMask() {
    // Input event listener
    document.addEventListener('input', function(event) {
        if (event.target.matches('.cell-amount-edit')) {
            applyMoneyMask(event);
        }
    });

    // Focus event listener
    document.addEventListener('focus', function(event) {
        if (event.target.matches('.cell-amount-edit')) {
            if (!event.target.hasAttribute('data-first-focus-done')) {
                event.target.setAttribute('data-first-focus-done', 'true');
                setTimeout(function() {
                    event.target.setSelectionRange(event.target.value.length, event.target.value.length);
                }, 0);
            }
        }
    }, true);

    // Blur event listener
    document.addEventListener('blur', function(event) {
        if (event.target.matches('.cell-amount-edit')) {
            event.target.removeAttribute('data-first-focus-done');
        }
    }, true);

    // Initialize existing inputs
    document.querySelectorAll('.cell-amount-edit').forEach(function(input) {
        if (input.value && input.value.trim() !== '') {
            let value = input.value.replace(',', '.');
            let num = parseFloat(value);
            if (!isNaN(num)) {
                let cents = Math.round(num * 100);
                let integerPart = Math.floor(cents / 100).toString();
                let decimalPart = (cents % 100).toString().padStart(2, '0');
                integerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, thousandSeparator);
                input.value = integerPart + decimalSeparator + decimalPart;
            } else {
                input.value = '0' + decimalSeparator + '00';
            }
        } else {
            input.value = '0' + decimalSeparator + '00';
        }
    });
}

// ===== BALANCE MANAGEMENT FUNCTIONS =====
// These functions are exposed globally for event_delegation.js

window.addNewBalance = function() {
    const template = document.getElementById('new-balance-template');
    const emptyRow = document.getElementById('balance-empty-row');
    if (emptyRow) emptyRow.style.display = 'none';
    template.style.display = '';
    template.querySelector('.cell-description-edit').focus();
};

window.cancelNewBalance = function() {
    const template = document.getElementById('new-balance-template');
    const tbody = document.getElementById('bank-balance-tbody');
    const emptyRow = document.getElementById('balance-empty-row');

    template.style.display = 'none';

    template.querySelector('.cell-description-edit').value = '';
    template.querySelector('.cell-amount-edit').value = '0' + decimalSeparator + '00';
    template.querySelector('.cell-date-edit').value = window.BANK_RECON_CONFIG.startDate;
    const memberSelect = template.querySelector('.cell-member-edit');
    if (memberSelect) memberSelect.value = '';

    const dataRows = tbody.querySelectorAll('tr[data-balance-id]:not(#new-balance-template)');
    if (dataRows.length === 0 && emptyRow) {
        emptyRow.style.display = '';
    }
};

window.toggleEditBalance = function(rowId, edit) {
    const row = document.getElementById(rowId);
    row.setAttribute('data-mode', edit ? 'edit' : 'display');

    const displayElements = row.querySelectorAll('.cell-description-display, .cell-amount-display, .cell-date-display, .cell-member-display, .actions-display');
    const editElements = row.querySelectorAll('.cell-description-edit, .cell-amount-edit, .cell-date-edit, .cell-member-edit, .actions-edit');

    displayElements.forEach(el => el.classList.toggle('hidden', edit));
    editElements.forEach(el => el.classList.toggle('hidden', !edit));

    if (edit) {
        const amountInput = row.querySelector('.cell-amount-edit');
        // Remove thousand separators first, then replace decimal separator with dot
        let rawValue = amountInput.value.replace(new RegExp('\\' + thousandSeparator, 'g'), '');
        rawValue = rawValue.replace(decimalSeparator, '.');
        const num = parseFloat(rawValue);
        if (!isNaN(num)) {
            const cents = Math.round(num * 100);
            const integerPart = Math.floor(cents / 100).toString();
            const decimalPart = (cents % 100).toString().padStart(2, '0');
            const formatted = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, thousandSeparator) + decimalSeparator + decimalPart;
            amountInput.value = formatted;
        }
    }
};

window.saveBalance = function(rowId) {
    const row = document.getElementById(rowId);
    const balanceId = row.getAttribute('data-balance-id');
    const isNew = balanceId === 'new';

    const description = row.querySelector('.cell-description-edit').value.trim();
    const amount = getRawValue(row.querySelector('.cell-amount-edit').value, thousandSeparator, decimalSeparator);
    const date = row.querySelector('.cell-date-edit').value;
    const memberSelect = row.querySelector('.cell-member-edit');
    const memberId = memberSelect ? memberSelect.value : null;

    if (!description) {
        alert(window.BANK_RECON_CONFIG.i18n.pleaseEnterDescription);
        return;
    }

    const data = {
        id: isNew ? null : balanceId,
        description: description,
        amount: amount,
        date: date,
        member_id: memberId,
        period_start_date: window.BANK_RECON_CONFIG.startDate
    };

    fetch(window.BANK_RECON_CONFIG.urls.saveBankBalance, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            if (isNew) {
                location.reload(); // Simple reload for new item for now
            } else {
                updateRow(row, data);
                window.toggleEditBalance(rowId, false);
                updateReconciliationSummary();
            }
        } else {
            alert(window.BANK_RECON_CONFIG.i18n.errorSavingBalance + ' ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert(window.BANK_RECON_CONFIG.i18n.networkErrorOccurred);
    });
};

function updateRow(row, data) {
    row.querySelector('.cell-description-display').textContent = data.description;
    row.querySelector('.cell-date-display').textContent = new Date(data.date + 'T00:00:00').toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
    row.querySelector('.cell-amount-display').textContent = formatCurrency(data.amount, currencySymbol, thousandSeparator, decimalSeparator);

    if (row.querySelector('.cell-member-display')) {
        row.querySelector('.cell-member-display').textContent = data.member_name || 'Family';
        row.querySelector('.cell-member-display').setAttribute('data-member-id', data.member_id || '');
    }

    // Update edit fields as well
    row.querySelector('.cell-description-edit').value = data.description;
    row.querySelector('.cell-date-edit').value = data.date;
    row.querySelector('.cell-amount-edit').value = data.amount;
    if (row.querySelector('.cell-member-edit')) {
        row.querySelector('.cell-member-edit').value = data.member_id || '';
    }
}

window.deleteBalance = function(balanceId) {
    // Use GenericModal.confirm instead of native confirm()
    window.GenericModal.confirm(
        window.BANK_RECON_CONFIG.i18n.deleteConfirm,
        function() {
            // User confirmed - proceed with deletion
            fetch(window.BANK_RECON_CONFIG.urls.deleteBankBalance, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken,
                },
                body: JSON.stringify({ id: balanceId })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    document.getElementById('balance-row-' + balanceId).remove();
                    updateReconciliationSummary();
                } else {
                    window.GenericModal.alert(window.BANK_RECON_CONFIG.i18n.errorDeletingBalance + ' ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                window.GenericModal.alert(window.BANK_RECON_CONFIG.i18n.networkErrorOccurred);
            });
        },
        window.BANK_RECON_CONFIG.i18n.deleteConfirmTitle || 'Confirm Deletion'
    );
};

function updateReconciliationSummary() {
    const urlParams = new URLSearchParams(window.location.search);
    const period = urlParams.get('period') || window.BANK_RECON_CONFIG.startDate;
    const mode = urlParams.get('mode') || 'general';
    const baseUrl = window.BANK_RECON_CONFIG.urls.getReconciliationSummary;
    const url = `${baseUrl}?period=${period}&mode=${mode}`;

    fetch(url)
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            const summary = data.reconciliation_data;
            if (summary.mode === 'general') {
                document.getElementById('reconciliation-total-income').textContent = formatCurrency(summary.total_income, currencySymbol, thousandSeparator, decimalSeparator);
                document.getElementById('reconciliation-total-expenses').textContent = formatCurrency(summary.total_expenses, currencySymbol, thousandSeparator, decimalSeparator);
                document.getElementById('reconciliation-calculated-balance').textContent = formatCurrency(summary.calculated_balance, currencySymbol, thousandSeparator, decimalSeparator);
                document.getElementById('reconciliation-calculated-balance-2').textContent = formatCurrency(summary.calculated_balance, currencySymbol, thousandSeparator, decimalSeparator);
                document.getElementById('reconciliation-bank-balance').textContent = formatCurrency(summary.total_bank_balance, currencySymbol, thousandSeparator, decimalSeparator);
                document.getElementById('total-bank-balance').textContent = formatCurrency(summary.total_bank_balance, currencySymbol, thousandSeparator, decimalSeparator);
                document.getElementById('reconciliation-discrepancy').textContent = formatCurrency(summary.discrepancy, currencySymbol, thousandSeparator, decimalSeparator);
                document.getElementById('reconciliation-discrepancy-percentage').textContent = `(${parseFloat(summary.discrepancy_percentage).toFixed(2)}%)`;

                const discrepancy_val = parseFloat(summary.discrepancy);
                const discrepancy_el = document.getElementById('reconciliation-discrepancy');
                discrepancy_el.classList.toggle('text-green-600', discrepancy_val >= 0);
                discrepancy_el.classList.toggle('dark:text-green-500', discrepancy_val >= 0);
                discrepancy_el.classList.toggle('text-red-600', discrepancy_val < 0);
                discrepancy_el.classList.toggle('dark:text-red-500', discrepancy_val < 0);

                // Update warning
                const warningContainer = document.getElementById('reconciliation-warning-container');
                if (summary.has_warning) {
                    warningContainer.innerHTML = `
                    <div class="bg-yellow-50 dark:bg-yellow-900/20 border-l-4 border-yellow-500 p-4">
                        <div class="flex items-center">
                            <span class="material-symbols-outlined text-yellow-500 mr-3">warning</span>
                            <div>
                                <h4 class="text-sm font-semibold text-yellow-800 dark:text-yellow-500">${window.BANK_RECON_CONFIG.i18n.warningDiscrepancyDetected}</h4>
                                <p class="text-sm text-yellow-700 dark:text-yellow-400 mt-1">
                                    ${window.BANK_RECON_CONFIG.i18n.warningDiscrepancyMessage}
                                </p>
                            </div>
                        </div>
                    </div>`;
                } else {
                    warningContainer.innerHTML = `
                    <div class="bg-green-50 dark:bg-green-900/20 border-l-4 border-green-500 p-4">
                        <div class="flex items-center">
                            <span class="material-symbols-outlined text-green-500 mr-3">check_circle</span>
                            <div>
                                <h4 class="text-sm font-semibold text-green-800 dark:text-green-500">${window.BANK_RECON_CONFIG.i18n.reconciliationOk}</h4>
                                <p class="text-sm text-green-700 dark:text-green-400 mt-1">
                                    ${window.BANK_RECON_CONFIG.i18n.reconciliationOkMessage}
                                </p>
                            </div>
                        </div>
                    </div>`;
                }

            } else { // detailed mode
                summary.members_data.forEach(memberData => {
                    const container = document.getElementById(`member-reconciliation-${memberData.member_id}`);
                    if (container) {
                        container.querySelector('.reconciliation-member-income').textContent = formatCurrency(memberData.income, currencySymbol, thousandSeparator, decimalSeparator);
                        container.querySelector('.reconciliation-member-expenses').textContent = formatCurrency(memberData.expenses, currencySymbol, thousandSeparator, decimalSeparator);
                        container.querySelector('.reconciliation-member-calculated').textContent = formatCurrency(memberData.calculated_balance, currencySymbol, thousandSeparator, decimalSeparator);
                        container.querySelector('.reconciliation-member-calculated-2').textContent = formatCurrency(memberData.calculated_balance, currencySymbol, thousandSeparator, decimalSeparator);
                        container.querySelector('.reconciliation-member-bank').textContent = formatCurrency(memberData.bank_balance, currencySymbol, thousandSeparator, decimalSeparator);
                        container.querySelector('.reconciliation-member-discrepancy').textContent = formatCurrency(memberData.discrepancy, currencySymbol, thousandSeparator, decimalSeparator);
                        container.querySelector('.reconciliation-member-discrepancy-percentage').textContent = `(${parseFloat(memberData.discrepancy_percentage).toFixed(2)}%)`;

                        const discrepancy_val = parseFloat(memberData.discrepancy);
                        const discrepancy_el = container.querySelector('.reconciliation-member-discrepancy');
                        discrepancy_el.classList.toggle('text-green-600', discrepancy_val >= 0);
                        discrepancy_el.classList.toggle('dark:text-green-500', discrepancy_val >= 0);
                        discrepancy_el.classList.toggle('text-red-600', discrepancy_val < 0);
                        discrepancy_el.classList.toggle('dark:text-red-500', discrepancy_val < 0);

                        const warningContainer = container.querySelector('.reconciliation-member-warning-container');
                        if(memberData.has_warning) {
                             warningContainer.innerHTML = `
                            <div class="bg-yellow-50 dark:bg-yellow-900/20 border-l-4 border-yellow-500 p-3 mt-4">
                                <div class="flex items-center">
                                    <span class="material-symbols-outlined text-yellow-500 mr-2 text-base">warning</span>
                                    <p class="text-xs text-yellow-700 dark:text-yellow-400">
                                        ${window.BANK_RECON_CONFIG.i18n.discrepancyExceedsMember}
                                    </p>
                                </div>
                            </div>`;
                        } else {
                            warningContainer.innerHTML = '';
                        }
                    }
                });
            }
        }
    });
}

// ===== RECONCILIATION MODE TOGGLE =====

window.toggleReconciliationMode = function(isDetailed) {
    const mode = isDetailed ? 'detailed' : 'general';
    console.log('[BankReconciliation] Toggling mode to:', mode);

    fetch(window.BANK_RECON_CONFIG.urls.toggleReconciliationMode, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ mode: mode })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            console.log('[BankReconciliation] Mode changed successfully to:', data.mode);
            // Reload page to apply new mode
            const urlParams = new URLSearchParams(window.location.search);
            urlParams.set('mode', data.mode);
            window.location.search = urlParams.toString();
        } else {
            console.error('[BankReconciliation] Error changing mode:', data.error);
            // Revert toggle on error
            const toggle = document.getElementById('mode-toggle');
            if (toggle) {
                toggle.checked = !isDetailed;
            }
        }
    })
    .catch(error => {
        console.error('[BankReconciliation] Fetch error:', error);
        // Revert toggle on error
        const toggle = document.getElementById('mode-toggle');
        if (toggle) {
            toggle.checked = !isDetailed;
        }
    });
};

// ===== REAL-TIME SYNCHRONIZATION =====

window.BankReconciliationRealtime = {

    /**
     * Handle bank balance created/updated from another user
     */
    updateBalance: function(balanceData) {
        console.log('[BankRecon RT] Updating balance:', balanceData);

        // Check if we're on the bank reconciliation page
        if (!document.getElementById('bank-balance-tbody')) {
            return;
        }

        const row = document.querySelector(`tr[data-balance-id="${balanceData.id}"]`);

        if (row) {
            // Update existing row using the data format expected by updateRow()
            const data = {
                description: balanceData.description,
                amount: balanceData.amount,
                date: balanceData.date,
                member_id: balanceData.member_id,
                member_name: balanceData.member_name
            };

            updateRow(row, data);

            // Highlight the updated row
            if (window.RealtimeUI && window.RealtimeUI.utils && window.RealtimeUI.utils.highlightElement) {
                window.RealtimeUI.utils.highlightElement(row, 2000);
            }
        } else {
            // New balance created by another user - reload page to show it
            console.log('[BankRecon RT] New balance detected, reloading page');
            location.reload();
        }

        // Update reconciliation totals
        if (typeof updateReconciliationSummary === 'function') {
            updateReconciliationSummary();
        }
    },

    /**
     * Handle bank balance deleted by another user
     */
    deleteBalance: function(balanceId) {
        console.log('[BankRecon RT] Deleting balance:', balanceId);

        const row = document.querySelector(`tr[data-balance-id="${balanceId}"]`);
        if (row) {
            // Fade out animation
            row.style.transition = 'opacity 0.3s ease';
            row.style.opacity = '0';

            setTimeout(() => {
                if (row.parentNode) {
                    row.parentNode.removeChild(row);

                    // Check if table is empty
                    const tbody = document.getElementById('bank-balance-tbody');
                    const dataRows = tbody.querySelectorAll('tr[data-balance-id]:not(#new-balance-template)');
                    if (dataRows.length === 0) {
                        const emptyRow = document.getElementById('balance-empty-row');
                        if (emptyRow) {
                            emptyRow.style.display = '';
                        }
                    }
                }
            }, 300);
        }

        // Update reconciliation totals
        if (typeof updateReconciliationSummary === 'function') {
            updateReconciliationSummary();
        }
    },

    /**
     * Handle mode change from another user
     */
    handleModeChange: function(data) {
        console.log('[BankReconciliationRealtime] Mode change received:', data);

        const mode = data.mode;
        const toggle = document.getElementById('mode-toggle');

        if (!toggle) {
            console.warn('[BankReconciliationRealtime] Mode toggle not found');
            return;
        }

        // Update toggle state
        const shouldBeChecked = (mode === 'detailed');
        if (toggle.checked !== shouldBeChecked) {
            toggle.checked = shouldBeChecked;

            // Reload page to apply new mode
            const urlParams = new URLSearchParams(window.location.search);
            urlParams.set('mode', mode);
            window.location.search = urlParams.toString();
        }
    }
};

function initRealtimeListeners() {
    // Listen for real-time bank balance events
    document.addEventListener('realtime:bankbalance:updated', function(event) {
        if (window.BankReconciliationRealtime && window.BankReconciliationRealtime.updateBalance) {
            window.BankReconciliationRealtime.updateBalance(event.detail.data);
        }
    });

    document.addEventListener('realtime:bankbalance:deleted', function(event) {
        if (window.BankReconciliationRealtime && window.BankReconciliationRealtime.deleteBalance) {
            window.BankReconciliationRealtime.deleteBalance(event.detail.data.id);
        }
    });

    console.log('[BankReconciliationRealtime] Loaded successfully');
}

console.log('[BankReconciliation.js] Loaded successfully');
