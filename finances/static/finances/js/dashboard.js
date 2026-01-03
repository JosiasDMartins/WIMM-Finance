/**
 * Dashboard Main Script
 * External JavaScript file (CSP compliant - no inline scripts)
 * Version: 20260101-001 - Added YTD real-time update debug logs
 */

'use strict';

function initDashboard() {
// Read configuration from data attributes
const config = document.getElementById('dashboard-config');
if (!config) {
    console.error('[Dashboard] Configuration element not found!');
    return;
}

// Extract configuration
window.DASHBOARD_CONFIG = {
    incomeFlowGroupId: config.dataset.incomeFlowgroupId,
    memberRole: config.dataset.memberRole,
    decimalSeparator: config.dataset.decimalSeparator,
    thousandSeparator: config.dataset.thousandSeparator,
    currencySymbol: config.dataset.currencySymbol,
    periodsHistory: JSON.parse(config.dataset.periodsHistory || '[]'),
    urls: {
        deleteItem: config.dataset.urlDeleteItem,
        saveItem: config.dataset.urlSaveItem,
        reorderIncome: config.dataset.urlReorderIncome,
        reorderFlowgroups: config.dataset.urlReorderFlowgroups,
        balanceSummary: config.dataset.urlBalanceSummary
    },
    i18n: {
        deleteConfirm: config.dataset.i18nDeleteConfirm,
        descriptionRequired: config.dataset.i18nDescriptionRequired,
        errorSaving: config.dataset.i18nErrorSaving,
        errorDeleting: config.dataset.i18nErrorDeleting,
        errorNetwork: config.dataset.i18nErrorNetwork,
        errorSavingOrder: config.dataset.i18nErrorSavingOrder,
        networkErrorOrder: config.dataset.i18nNetworkErrorOrder,
        errorSavingIncome: config.dataset.i18nErrorSavingIncome,
        errorUpdatingStatus: config.dataset.i18nErrorUpdatingStatus,
        onlyParentsChange: config.dataset.i18nOnlyParentsChange,
        others: config.dataset.i18nOthers,
        totalExpenses: config.dataset.i18nTotalExpenses,
        trend: config.dataset.i18nTrend,
        overBudget: config.dataset.i18nOverBudget,
        noExpenseGroups: config.dataset.i18nNoExpenseGroups
    }
};

console.log('[Dashboard] Configuration loaded:', window.DASHBOARD_CONFIG);

// Initialize dashboard components
initUtilities();
initCharts();
initDragAndDrop();
initEventHandlers();
initMobileKeyboardHandling();
}

// ===== UTILITY FUNCTIONS =====

function initUtilities() {
    // Utility for getting CSRF token
    // getCookie is now provided by utils.js
    window.csrftoken = window.getCookie('csrftoken');

    // Shortcuts to config
    const cfg = window.DASHBOARD_CONFIG;
    window.incomeFlowGroupId = cfg.incomeFlowGroupId;
    window.memberRoleForPeriod = cfg.memberRole;
    window.decimalSeparator = cfg.decimalSeparator;
    window.thousandSeparator = cfg.thousandSeparator;

    console.log('[INIT] decimalSeparator:', window.decimalSeparator, 'thousandSeparator:', window.thousandSeparator);
}

function initCharts() {
    // Charts will be initialized here
    console.log('[Dashboard] Initializing charts...');
    if (typeof Chart !== 'undefined') {
        initPieChart();
        initBarChart();
        updateKeyMetrics();
    } else {
        console.error('[Dashboard] Chart.js not loaded!');
    }
}

function initEventHandlers() {
    // Event handlers are managed by event_delegation.js
    console.log('[Dashboard] Event handlers delegated to event_delegation.js');

    // Add money mask to all amount fields using event delegation
    document.addEventListener('input', function(event) {
        if (event.target.matches('input[data-field="amount"]')) {
            applyMoneyMask(event, thousandSeparator, decimalSeparator);
        }
    });

    // Initialize cursor positioning for amount inputs (from utils.js)
    if (typeof initializeCursorPositioning === 'function') {
        initializeCursorPositioning('input[data-field="amount"]');
        console.log('[Dashboard] Cursor positioning initialized for amount inputs');
    } else {
        console.error('[Dashboard] initializeCursorPositioning not found in utils.js!');
    }

    // Also manually add cursor positioning for income amount fields (fallback)
    document.addEventListener('focus', function(event) {
        if (event.target.matches('input[data-field="amount"]')) {
            if (!event.target.hasAttribute('data-cursor-initialized')) {
                event.target.setAttribute('data-cursor-initialized', 'true');
                setTimeout(function() {
                    const len = event.target.value.length;
                    event.target.setSelectionRange(len, len);
                    console.log('[Dashboard] Cursor positioned to right for:', event.target);
                }, 0);
            }
        }
    }, true);

    // Reset cursor flag on blur
    document.addEventListener('blur', function(event) {
        if (event.target.matches('input[data-field="amount"]')) {
            event.target.removeAttribute('data-cursor-initialized');
        }
    }, true);
}

function initDragAndDrop() {
    // Drag and drop initialization
    console.log('[Dashboard] Initializing drag and drop...');
    initExpenseGroupsDragDrop();
    initIncomeItemsDragDrop();
}

function initMobileKeyboardHandling() {
    // Mobile keyboard handling
    console.log('[Dashboard] Initializing mobile keyboard handling...');
    // Handled below in separate function
}

function initExpenseGroupsDragDrop() {
    console.log('[Dashboard] Expense groups drag & drop ready');
    initializeDragAndDrop();
    initializeClickableRows();
}

function initIncomeItemsDragDrop() {
    console.log('[Dashboard] Income items drag & drop ready');
    initializeDragAndDropIncome();
}

function updateKeyMetrics() {
    updateMetrics();
}

// ===== UTILITY FUNCTIONS =====

// Function to format number as currency for display
// formatCurrency - using utils.js

// Function to parse localized currency string back to number
function parseCurrency(text) {
    if (!text) return 0;

    // Remove currency symbol and whitespace
    let cleanText = text.replace(/[^\d.,\-]/g, '');

    // Replace thousand separator with empty string
    // Replace decimal separator with dot for parseFloat
    cleanText = cleanText.replace(new RegExp('\\' + thousandSeparator, 'g'), '');
    cleanText = cleanText.replace(new RegExp('\\' + decimalSeparator, 'g'), '.');

    const num = parseFloat(cleanText);
    return isNaN(num) ? 0 : num;
}

// === CHARTS INITIALIZATION ===

// Chart.js default colors
const chartColors = [
    'rgb(239, 68, 68)',   // red-500
    'rgb(249, 115, 22)',  // orange-500
    'rgb(234, 179, 8)',   // yellow-500
    'rgb(34, 197, 94)',   // green-500
    'rgb(59, 130, 246)',  // blue-500
    'rgb(168, 85, 247)',  // purple-500
    'rgb(236, 72, 153)',  // pink-500
];

let pieChart, barChart;

// Initialize Pie Chart
function initPieChart() {
    const ctx = document.getElementById('expensesPieChart');
    if (!ctx) return;

    // Destroy existing chart if it exists to prevent canvas reuse error
    if (pieChart) {
        pieChart.destroy();
    }

    const expenseData = getTop3ExpensesData();

    pieChart = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: expenseData.labels,
            datasets: [{
                data: expenseData.values,
                backgroundColor: chartColors,
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${label}: $${formatCurrency(value, '', thousandSeparator, decimalSeparator)} (${percentage}%)`;
                        }
                    }
                }
            },
            layout: {
                padding: {
                    left: 5,
                    right: 5,
                    top: 5,
                    bottom: 5
                }
            }
        }
    });
}

// Calculate linear regression for trend line
function calculateTrendLine(values) {
    const n = values.length;
    if (n === 0) return [];
    
    const xValues = values.map((_, i) => i);
    const sumX = xValues.reduce((a, b) => a + b, 0);
    const sumY = values.reduce((a, b) => a + b, 0);
    const sumXY = xValues.reduce((sum, x, i) => sum + x * values[i], 0);
    const sumX2 = xValues.reduce((sum, x) => sum + x * x, 0);
    
    const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
    const intercept = (sumY - slope * sumX) / n;
    
    return xValues.map(x => slope * x + intercept);
}

// Initialize Bar Chart with dynamic colors and trend line
function initBarChart() {
    const ctx = document.getElementById('expensesBarChart');
    if (!ctx) return;

    // Destroy existing chart if it exists to prevent canvas reuse error
    if (barChart) {
        barChart.destroy();
    }

    const barData = window.DASHBOARD_CONFIG.periodsHistory;

    // Calculate bar colors based on income commitment
    const barColors = barData.colors || barData.values.map(() => 'rgb(239, 68, 68)');

    // Calculate trend line
    const trendLine = calculateTrendLine(barData.values);

    barChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: barData.labels,
            datasets: [
                {
                    label: window.DASHBOARD_CONFIG.i18n.totalExpenses,
                    data: barData.values,
                    backgroundColor: barColors,
                    borderColor: barColors.map(color => color.replace('rgb', 'rgba').replace(')', ', 0.8)')),
                    borderWidth: 1
                },
                {
                    label: window.DASHBOARD_CONFIG.i18n.trend,
                    data: trendLine,
                    type: 'line',
                    borderColor: 'rgb(59, 130, 246)',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    pointRadius: 0,
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '$' + formatCurrency(value, '', thousandSeparator, decimalSeparator);
                        }
                    }
                },
                x: {
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45,
                        font: {
                            size: 9
                        }
                    }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        font: {
                            size: 10
                        },
                        boxWidth: 12,
                        padding: 8
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            if (context.datasetIndex === 0) {
                                return 'Total: $' + formatCurrency(context.parsed.y, '', thousandSeparator, decimalSeparator);
                            } else {
                                return 'Trend: $' + formatCurrency(context.parsed.y, '', thousandSeparator, decimalSeparator);
                            }
                        }
                    }
                }
            },
            layout: {
                padding: {
                    left: 5,
                    right: 5,
                    top: 5,
                    bottom: 5
                }
            }
        }
    });
}

// Get Top 3 Expenses Data (based on realized values only)
function getTop3ExpensesData() {
    const expenseRows = document.querySelectorAll('tbody tr[data-group-id]');
    const expenses = [];

    expenseRows.forEach(row => {
        // Get the first cell (after drag handle) which contains the group name
        const nameCell = row.querySelectorAll('td')[1]; // Second td (index 1)
        const nameText = nameCell.textContent.trim();
        // Get only the first line (group name) before any badges/labels
        const name = nameText.split('\n')[0].trim();

        // Use only realized values for the chart
        const realizedValue = parseFloat(row.querySelector('.group-realized').getAttribute('data-value')) || 0;

        if (realizedValue > 0) {
            expenses.push({ name, value: realizedValue });
        }
    });

    // Sort by value descending
    expenses.sort((a, b) => b.value - a.value);

    // Get top 3
    const top3 = expenses.slice(0, 3);
    const others = expenses.slice(3).reduce((sum, item) => sum + item.value, 0);

    const labels = top3.map(e => e.name);
    const values = top3.map(e => e.value);

    if (others > 0) {
        labels.push(window.DASHBOARD_CONFIG.i18n.others);
        values.push(others);
    }

    return { labels, values };
}

// Update Pie Chart
function updatePieChart() {
    if (!pieChart) return;
    
    const expenseData = getTop3ExpensesData();
    pieChart.data.labels = expenseData.labels;
    pieChart.data.datasets[0].data = expenseData.values;
    pieChart.update('none');
}

// Update metrics card (only dynamic values)
function updateMetrics() {
    // Highest expense (from current period)
    const expenseRows = document.querySelectorAll('tbody tr[data-group-id]');
    let highestExpense = 0;
    expenseRows.forEach(row => {
        const realizedValue = parseFloat(row.querySelector('.group-realized').getAttribute('data-value')) || 0;
        if (realizedValue > highestExpense) {
            highestExpense = realizedValue;
        }
    });
    document.getElementById('metric-highest').textContent = '$ ' + formatCurrency(highestExpense, '', thousandSeparator, decimalSeparator);

    // Current commitment percentage (current period only)
    const incomeElem = document.getElementById('balance-realized-income');
    const expenseElem = document.getElementById('balance-realized-expense');

    if (!incomeElem || !expenseElem) {
        console.error('Balance elements not found');
        return;
    }

    // Parse localized currency values
    const realizedIncome = parseCurrency(incomeElem.textContent);
    const realizedExpense = parseCurrency(expenseElem.textContent);

    const commitment = realizedIncome > 0 ? (realizedExpense / realizedIncome * 100) : 0;
    const commitmentElem = document.getElementById('metric-commitment');
    commitmentElem.textContent = commitment.toFixed(1) + '%';

    if (commitment >= 98) {
        commitmentElem.classList.remove('text-green-600', 'dark:text-green-500', 'text-yellow-600', 'dark:text-yellow-500');
        commitmentElem.classList.add('text-red-600', 'dark:text-red-500');
    } else if (commitment >= 90) {
        commitmentElem.classList.remove('text-green-600', 'dark:text-green-500', 'text-red-600', 'dark:text-red-500');
        commitmentElem.classList.add('text-yellow-600', 'dark:text-yellow-500');
    } else {
        commitmentElem.classList.remove('text-red-600', 'dark:text-red-500', 'text-yellow-600', 'dark:text-yellow-500');
        commitmentElem.classList.add('text-green-600', 'dark:text-green-500');
    }
}

// Money mask functions - using utils.js (applyMoneyMask, getRawValue)

// Note: Duplicate DOMContentLoaded listener removed
// Chart initialization is handled in initDashboard() -> initCharts()
// Money mask event delegation is handled in initEventHandlers()
// All initialization logic moved to the main DOMContentLoaded listener at the end of this file

// === END CHARTS ===

function updateBalanceSheet() {
    // Fetch updated balance from backend
    const urlParams = new URLSearchParams(window.location.search);
    const period = urlParams.get('period') || '';
    const url = window.DASHBOARD_CONFIG.urls.balanceSummary + (period ? `?period=${period}` : '');

    fetch(url, {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            const balance = data.balance;
            const symbol = balance.currency_symbol || '$';

            // Update income
            document.getElementById('balance-estimated-income').textContent = symbol + ' ' + formatCurrency(parseFloat(balance.estimated_income), '', thousandSeparator, decimalSeparator);
            document.getElementById('balance-realized-income').textContent = symbol + ' ' + formatCurrency(parseFloat(balance.realized_income), '', thousandSeparator, decimalSeparator);

            // Update expense
            document.getElementById('balance-estimated-expense').textContent = symbol + ' ' + formatCurrency(parseFloat(balance.estimated_expense), '', thousandSeparator, decimalSeparator);
            document.getElementById('balance-realized-expense').textContent = symbol + ' ' + formatCurrency(parseFloat(balance.realized_expense), '', thousandSeparator, decimalSeparator);

            // Update result
            const estimatedResult = parseFloat(balance.estimated_result);
            const realizedResult = parseFloat(balance.realized_result);

            const estResultCell = document.getElementById('balance-estimated-result');
            const realResultCell = document.getElementById('balance-realized-result');

            estResultCell.textContent = symbol + ' ' + formatCurrency(estimatedResult, '', thousandSeparator, decimalSeparator);
            realResultCell.textContent = symbol + ' ' + formatCurrency(realizedResult, '', thousandSeparator, decimalSeparator);

            // Update colors
            if (estimatedResult >= 0) {
                estResultCell.className = 'py-4 px-4 text-sm text-green-600 dark:text-green-500 font-bold';
            } else {
                estResultCell.className = 'py-4 px-4 text-sm text-red-600 dark:text-red-500 font-bold';
            }

            if (realizedResult >= 0) {
                realResultCell.className = 'py-4 px-4 text-sm text-green-600 dark:text-green-500 font-bold';
            } else {
                realResultCell.className = 'py-4 px-4 text-sm text-red-600 dark:text-red-500 font-bold';
            }

            // Update metrics
            updateMetrics();
        } else {
            console.error('Error fetching balance:', data.error);
        }
    })
    .catch(error => {
        console.error('Fetch Error:', error);
    });
}

// Function to add a new income row
window.addNewIncomeRow = function() {
    console.log('[addNewIncomeRow] Called');
    const emptyRow = document.getElementById('income-empty-row');
    if (emptyRow) {
        emptyRow.remove();
    }

    const templateRow = document.getElementById('new-income-template');
    if (!templateRow) {
        console.error('[addNewIncomeRow] Template not found');
        return;
    }

    const hasHiddenClass = templateRow.classList.contains('hidden');
    const computedDisplay = window.getComputedStyle(templateRow).display;
    const isHidden = hasHiddenClass || computedDisplay === 'none';

    console.log('[addNewIncomeRow] Template state - hasHiddenClass:', hasHiddenClass, 'computedDisplay:', computedDisplay, 'isHidden:', isHidden);

    if (isHidden) {
        console.log('[addNewIncomeRow] Showing template');
        templateRow.classList.remove('hidden');
        templateRow.style.display = '';
        templateRow.querySelector('input[data-field="description"]').focus();
    } else {
        console.log('[addNewIncomeRow] Template already visible, just focusing');
        templateRow.querySelector('input[data-field="description"]').focus();
    }
}

// Function to toggle income realized status (exposed globally for event_delegation.js)
window.toggleIncomeRealized = function(rowId) {
    const row = document.getElementById(rowId);
    const transactionId = row.getAttribute('data-item-id');

    if (transactionId === 'NEW') return;

    // Check if this is a kids income (should not be toggled)
    if (row.getAttribute('data-kids-income') === 'true') {
        alert(window.DASHBOARD_CONFIG.i18n.onlyParentsChange);
        return;
    }

    // Get current status from data attribute
    const currentStatus = row.getAttribute('data-realized') === 'true';
    const newStatus = !currentStatus;

    // Get other field values
    const description = row.querySelector('.cell-description-display').textContent.trim();
    const fullDate = row.getAttribute('data-date');

    // Get amount from edit input field and convert from masked format
    const amountInput = row.querySelector('.cell-amount-edit input[data-field="amount"]');
    const amountText = getRawValue(amountInput.value, thousandSeparator, decimalSeparator);
    const isFixed = row.getAttribute('data-is-fixed') === 'true';

    const data = {
        'flow_group_id': incomeFlowGroupId,
        'transaction_id': transactionId,
        'description': description,
        'amount': amountText,
        'date': fullDate,
        'realized': newStatus,
        'is_fixed': isFixed,
    };

    fetch(window.DASHBOARD_CONFIG.urls.saveItem, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Update toggle visual state
            const toggleBtn = row.querySelector('.income-realized-toggle');
            const toggleCircle = toggleBtn.querySelector('span');
            const amountDisplay = row.querySelector('.cell-amount-display');
            const amountCell = amountDisplay.parentElement;

            // Update data attributes
            row.setAttribute('data-realized', data.realized ? 'true' : 'false');
            row.setAttribute('data-amount', data.amount);

            // Update amount display with currency symbol
            if (data.amount && data.currency_symbol) {
                amountDisplay.textContent = data.currency_symbol + ' ' + formatCurrency(data.amount, '', thousandSeparator, decimalSeparator);
            }

            // Update amount input field
            const amountInput = row.querySelector('input[data-field="amount"]');
            if (amountInput && data.amount) {
                amountInput.value = formatAmountForInput(data.amount, thousandSeparator, decimalSeparator);
            }

            if (data.realized) {
                toggleBtn.classList.remove('bg-gray-300', 'dark:bg-gray-600');
                toggleBtn.classList.add('bg-green-500');
                toggleCircle.classList.add('translate-x-4');
                amountCell.classList.remove('text-gray-400', 'dark:text-gray-500');
                amountCell.classList.add('text-green-600', 'dark:text-green-500');
                // Update row background color
                row.classList.remove('row-not-realized-income');
                row.classList.add('row-realized-income');
            } else {
                toggleBtn.classList.remove('bg-green-500');
                toggleBtn.classList.add('bg-gray-300', 'dark:bg-gray-600');
                toggleCircle.classList.remove('translate-x-4');
                amountCell.classList.remove('text-green-600', 'dark:text-green-500');
                amountCell.classList.add('text-gray-400', 'dark:text-gray-500');
                // Update row background color
                row.classList.remove('row-realized-income');
                row.classList.add('row-not-realized-income');
            }

            // Update balance sheet
            updateBalanceSheet();
        } else {
            alert(window.DASHBOARD_CONFIG.i18n.errorUpdatingStatus + ' ' + data.error);
        }
    })
    .catch(error => {
        console.error('Fetch Error:', error);
        alert(window.DASHBOARD_CONFIG.i18n.errorNetwork);
    });
}

// Function to save new income item
window.saveIncomeItem = function(rowId) {
    const row = document.getElementById(rowId);

    // CRITICAL FIX: Prevent double save - check if already saving
    if (row.dataset.saving === 'true') {
        console.log('[saveIncomeItem] Already saving, ignoring duplicate call');
        return;
    }
    row.dataset.saving = 'true';

    // Check toggle state
    const toggleNew = row.querySelector('.income-realized-toggle-new');
    const realizedValue = toggleNew.classList.contains('bg-green-500');

    const amountValue = getRawValue(row.querySelector('input[data-field="amount"]').value, thousandSeparator, decimalSeparator);

    const data = {
        'flow_group_id': incomeFlowGroupId,
        'transaction_id': null,
        'description': row.querySelector('input[data-field="description"]').value,
        'amount': amountValue,  // Send raw value, backend handles locale
        'date': row.querySelector('input[data-field="date"]').value,
        'realized': realizedValue,
        'is_child_manual': memberRoleForPeriod === 'CHILD',  // Flag for child manual income
    };

    if (!data.description || !data.amount || !data.date) {
        alert(window.DASHBOARD_CONFIG.i18n.descriptionRequired);
        return;
    }

    fetch(window.DASHBOARD_CONFIG.urls.saveItem, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // FIXED: Don't manually add the row here - WebSocket will handle it
            // This prevents duplicate items (one from manual add + one from WebSocket broadcast)

            // Just hide and reset the template row
            cancelNewIncomeRow('new-income-template');

            // Update balance sheet (WebSocket will update after adding the row)
            // We do a small delay to ensure WebSocket has processed first
            setTimeout(() => {
                updateBalanceSheet();
            }, 100);

            // Reset saving flag
            row.dataset.saving = 'false';
        } else {
            alert(window.DASHBOARD_CONFIG.i18n.errorSavingIncome + ' ' + data.error);
            // Reset saving flag on error
            row.dataset.saving = 'false';
        }
    })
    .catch(error => {
        console.error('Fetch Error:', error);
        alert('window.DASHBOARD_CONFIG.i18n.errorNetwork');
        // Reset saving flag on error
        row.dataset.saving = 'false';
    });
}

// Function to cancel new income row
window.cancelNewIncomeRow = function(rowId) {
    console.log('[cancelNewIncomeRow] Called with rowId:', rowId);
    const row = document.getElementById(rowId);
    if (!row) {
        console.error('[cancelNewIncomeRow] Row not found');
        return;
    }

    console.log('[cancelNewIncomeRow] Before hide - classList:', row.classList.toString(), 'display:', row.style.display);

    // Hide the template
    row.classList.add('hidden');
    row.style.display = 'none';
    row.style.transform = 'translateX(0)';
    row.classList.remove('actions-revealed-income');

    console.log('[cancelNewIncomeRow] After hide - classList:', row.classList.toString(), 'display:', row.style.display);

    // Reset inputs
    row.querySelector('input[data-field="description"]').value = '';
    row.querySelector('input[data-field="amount"]').value = '0' + decimalSeparator + '00';

    // Reset toggle
    const toggleNew = row.querySelector('.income-realized-toggle-new');
    const toggleCircle = toggleNew.querySelector('span');
    toggleNew.classList.remove('bg-green-500');
    toggleNew.classList.add('bg-gray-300', 'dark:bg-gray-600');
    toggleCircle.classList.remove('translate-x-3');

    // Reset saving flag
    row.dataset.saving = 'false';

    console.log('[cancelNewIncomeRow] Template hidden and reset');
}

// Add click handler for new income toggle
document.addEventListener('DOMContentLoaded', function() {
    const toggleNew = document.querySelector('.income-realized-toggle-new');
    if (toggleNew) {
        toggleNew.addEventListener('click', function() {
            const toggleCircle = this.querySelector('span');
            if (this.classList.contains('bg-green-500')) {
                this.classList.remove('bg-green-500');
                this.classList.add('bg-gray-300', 'dark:bg-gray-600');
                toggleCircle.classList.remove('translate-x-3');
            } else {
                this.classList.remove('bg-gray-300', 'dark:bg-gray-600');
                this.classList.add('bg-green-500');
                toggleCircle.classList.add('translate-x-3');
            }
        });
    }
    
    // Tooltip functionality for child manual income
    const childIncomeRows = document.querySelectorAll('.child-manual-income-row');
    childIncomeRows.forEach(row => {
        const tooltip = row.querySelector('.child-income-tooltip');
        
        row.addEventListener('mouseenter', function() {
            tooltip.classList.remove('hidden');
        });
        
        row.addEventListener('mouseleave', function() {
            tooltip.classList.add('hidden');
        });
    });
});

// Function to delete an item (exposed globally for event_delegation.js)
window.deleteItem = async function(rowId) {
    const row = document.getElementById(rowId);
    const transactionId = row.getAttribute('data-item-id');

    if (transactionId === 'NEW') {
        cancelNewRow(rowId);
        return;
    }

    // Use GenericModal.confirm (returns Promise)
    const confirmed = await window.GenericModal.confirm(
        window.DASHBOARD_CONFIG.i18n.deleteConfirm || 'Are you sure you want to delete this item?',
        window.DASHBOARD_CONFIG.i18n.confirmDeleteTitle || 'Confirm Deletion'
    );

    if (!confirmed) {
        return; // User cancelled
    }

    // User confirmed - proceed with deletion
    fetch(window.DASHBOARD_CONFIG.urls.deleteItem, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({'transaction_id': transactionId})
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            row.remove();
            updateBalanceSheet();
            updatePieChart();
        } else {
            window.GenericModal.alert(window.DASHBOARD_CONFIG.i18n.errorDeleting + ' ' + data.error);
        }
    })
    .catch(error => {
        console.error('Fetch Error:', error);
        window.GenericModal.alert(window.DASHBOARD_CONFIG.i18n.errorNetwork);
    });
};

// Function to format amount for input field based on user's locale
// formatAmountForInput - using utils.js

// Function to toggle between display and edit mode
window.toggleEditMode = function(rowId, startEdit) {
    const row = document.getElementById(rowId);
    if (!row) return;

    const displayElements = row.querySelectorAll('.actions-display, .cell-description-display, .cell-date-display, .cell-amount-display');
    const editElements = row.querySelectorAll('.actions-edit, .cell-description-edit, .cell-date-edit, .cell-amount-edit');

    displayElements.forEach(el => el.classList.toggle('hidden', startEdit));
    editElements.forEach(el => el.classList.toggle('hidden', !startEdit));

    row.setAttribute('data-mode', startEdit ? 'edit' : 'display');

    // Mobile: Reset row position when entering/exiting edit mode
    if (window.matchMedia('(max-width: 768px)').matches) {
        row.style.transform = 'translateX(0)';
        row.classList.remove('actions-revealed-income');

        // CRITICAL FIX: Disable drag in edit mode, enable when exiting
        if (startEdit) {
            row.setAttribute('draggable', 'false');
        } else {
            row.setAttribute('draggable', 'true');
        }

        // Toggle drag handle visibility based on edit mode
        const dragHandle = row.querySelector('.drag-handle-cell-income');
        if (dragHandle) {
            const dragIcon = dragHandle.querySelector('.drag-handle-income');
            const checkIcon = dragHandle.querySelector('.edit-save-icon-income');

            if (startEdit) {
                // Show check icon, hide drag icon
                if (dragIcon) dragIcon.style.display = 'none';
                if (checkIcon) checkIcon.style.display = 'inline-block';

                // Update date input display value for mobile button-style input
                const dateInput = row.querySelector('.date-input-field-income');
                if (dateInput) {
                    const dateValue = dateInput.value; // YYYY-MM-DD format
                    if (dateValue) {
                        const [year, month, day] = dateValue.split('-');
                        const displayValue = `${day}/${month}`;
                        dateInput.setAttribute('data-display-value', displayValue);
                    }
                }
            } else {
                // Show drag icon, hide check icon
                if (dragIcon) dragIcon.style.display = 'inline-block';
                if (checkIcon) checkIcon.style.display = 'none';
            }
        }
    }

    if(startEdit) {
         row.querySelector('.cell-description-edit input').focus();
    }
}

// Function to save edited item
window.saveItem = function(rowId) {
    const row = document.getElementById(rowId);
    const transactionId = row.getAttribute('data-item-id');
    const realizedStatus = row.getAttribute('data-realized') === 'true';

    const amountInput = row.querySelector('input[data-field="amount"]');
    const amountText = getRawValue(amountInput.value, thousandSeparator, decimalSeparator);

    const data = {
        'flow_group_id': incomeFlowGroupId,
        'transaction_id': transactionId,
        'description': row.querySelector('input[data-field="description"]').value,
        'amount': amountText,  // Send raw value in standard format
        'date': row.querySelector('input[data-field="date"]').value,
        'realized': realizedStatus,
    };
    
    if (!data.description || !data.amount || !data.date) {
        alert(window.DASHBOARD_CONFIG.i18n.descriptionRequired);
        return;
    }

    fetch(window.DASHBOARD_CONFIG.urls.saveItem, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Update row data
            row.setAttribute('data-amount', data.amount);
            row.querySelector('.cell-description-display').textContent = data.description;
            // Use currency_symbol from backend response
            const currencySymbol = data.currency_symbol || 'window.DASHBOARD_CONFIG.currencySymbol';
            row.querySelector('.cell-amount-display').textContent = currencySymbol + ' ' + formatCurrency(data.amount, '', thousandSeparator, decimalSeparator);
            row.querySelector('.cell-date-display').textContent = new Date(data.date).toLocaleDateString('en-GB', {day: '2-digit', month: '2-digit'});

            // Update inputs
            row.querySelector('input[data-field="description"]').value = data.description;
            row.querySelector('input[data-field="amount"]').value = formatAmountForInput(data.amount, thousandSeparator, decimalSeparator);
            row.querySelector('input[data-field="date"]').value = data.date;
            row.setAttribute('data-date', data.date);
            
            toggleEditMode(rowId, false);
            updateBalanceSheet();
        } else {
            alert('window.DASHBOARD_CONFIG.i18n.errorSaving ' + data.error);
        }
    })
    .catch(error => {
        console.error('Fetch Error:', error);
        alert('window.DASHBOARD_CONFIG.i18n.errorNetwork');
    });
}

// === DRAG AND DROP REORDERING FOR EXPENSE GROUPS ===

let draggedRow = null;
let draggedOverRow = null;

// Initialize drag and drop on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeDragAndDrop();
    initializeClickableRows();
    initializeDragAndDropIncome();
});

function initializeDragAndDrop() {
    const tbody = document.getElementById('expense-groups-tbody');
    if (!tbody) return;

    const rows = tbody.querySelectorAll('tr.draggable-row');

    rows.forEach(row => {
        row.addEventListener('dragstart', handleDragStart);
        row.addEventListener('dragover', handleDragOver);
        row.addEventListener('dragenter', handleDragEnter);
        row.addEventListener('dragleave', handleDragLeave);
        row.addEventListener('drop', handleDrop);
        row.addEventListener('dragend', handleDragEnd);
    });
}

function initializeClickableRows() {
    const tbody = document.getElementById('expense-groups-tbody');
    if (!tbody) return;

    const rows = tbody.querySelectorAll('tr.group-row-clickable');

    rows.forEach(row => {
        // Make row clickable (except drag handle)
        row.addEventListener('click', function(e) {
            // Don't navigate if clicking on drag handle
            if (e.target.closest('.drag-handle-cell') || e.target.closest('.drag-handle')) {
                return;
            }

            const url = this.getAttribute('data-group-url');
            if (url) {
                window.location.href = url;
            }
        });

        // Add cursor pointer on hover (except drag handle)
        row.addEventListener('mouseover', function(e) {
            if (!e.target.closest('.drag-handle-cell') && !e.target.closest('.drag-handle')) {
                this.style.cursor = 'pointer';
            }
        });

        row.addEventListener('mouseout', function(e) {
            this.style.cursor = 'default';
        });
    });

    // Prevent drag on non-drag-handle clicks
    const dragHandles = tbody.querySelectorAll('.drag-handle');
    dragHandles.forEach(handle => {
        handle.addEventListener('mousedown', function(e) {
            const row = this.closest('tr');
            if (row) {
                row.setAttribute('draggable', 'true');
            }
        });

        // CORREÇÃO: Touch support for mobile drag
        handle.addEventListener('touchstart', function(e) {
            const row = this.closest('tr');
            if (row) {
                row.setAttribute('draggable', 'true');
                handleTouchDragStartGroups(e, row);
            }
        }, { passive: false });
    });

    // Disable dragging when not on handle
    rows.forEach(row => {
        row.addEventListener('mousedown', function(e) {
            if (!e.target.closest('.drag-handle-cell') && !e.target.closest('.drag-handle')) {
                this.setAttribute('draggable', 'false');
            } else {
                this.setAttribute('draggable', 'true');
            }
        });

        // CORREÇÃO: Adicionar touch event listeners para mobile
        row.addEventListener('touchmove', handleTouchDragMoveGroups, { passive: false });
        row.addEventListener('touchend', handleTouchDragEndGroups, { passive: false });
    });
}

// CORREÇÃO: Variáveis para mobile drag de FlowGroups
let touchDraggedGroupRow = null;
let touchStartYGroups = 0;
let touchCurrentYGroups = 0;

function handleTouchDragStartGroups(e, row) {
    if (!e.target.closest('.drag-handle')) return;

    e.preventDefault();
    touchDraggedGroupRow = row;
    touchStartYGroups = e.touches[0].clientY;
    touchCurrentYGroups = touchStartYGroups;

    // Visual feedback
    row.style.opacity = '0.4';
    row.classList.add('dragging');

    // Disable pointer events on other rows to prevent conflicts
    document.querySelectorAll('tr.draggable-row').forEach(r => {
        if (r !== row) {
            r.style.pointerEvents = 'none';
        }
    });
}

function handleTouchDragMoveGroups(e) {
    if (!touchDraggedGroupRow) return;
    if (this !== touchDraggedGroupRow) return;

    e.preventDefault();
    touchCurrentYGroups = e.touches[0].clientY;

    const deltaY = touchCurrentYGroups - touchStartYGroups;

    // Find the row under the touch point
    const elementBelow = document.elementFromPoint(
        e.touches[0].clientX,
        e.touches[0].clientY
    );

    const rowBelow = elementBelow ? elementBelow.closest('tr.draggable-row') : null;

    // Remove previous highlights
    document.querySelectorAll('tr.draggable-row').forEach(r => {
        r.classList.remove('border-t-2', 'border-primary', 'border-b-2');
    });

    // Highlight the target row
    if (rowBelow && rowBelow !== touchDraggedGroupRow) {
        if (deltaY > 0) {
            // Dragging down
            rowBelow.classList.add('border-b-2', 'border-primary');
        } else {
            // Dragging up
            rowBelow.classList.add('border-t-2', 'border-primary');
        }
    }

    // Visual feedback - move the row
    touchDraggedGroupRow.style.transform = `translateY(${deltaY}px)`;
}

function handleTouchDragEndGroups(e) {
    if (!touchDraggedGroupRow) return;
    if (this !== touchDraggedGroupRow) return;

    e.preventDefault();

    const deltaY = touchCurrentYGroups - touchStartYGroups;

    const rect = touchDraggedGroupRow.getBoundingClientRect();
    const centerX = rect.left + (rect.width / 2);

    touchDraggedGroupRow.style.visibility = 'hidden';
    const elementBelow = document.elementFromPoint(centerX, touchCurrentYGroups);
    touchDraggedGroupRow.style.visibility = '';

    let targetRow = elementBelow ? elementBelow.closest('tr.draggable-row') : null;

    if (!targetRow) {
        const tbody = document.getElementById('expense-groups-tbody');
        const allRows = Array.from(tbody.querySelectorAll('tr.draggable-row'));

        let closestRow = null;
        let closestDistance = Infinity;

        allRows.forEach(function(row) {
            if (row === touchDraggedGroupRow) return;

            const rowRect = row.getBoundingClientRect();
            const rowCenterY = rowRect.top + (rowRect.height / 2);
            const distance = Math.abs(touchCurrentYGroups - rowCenterY);

            if (distance < closestDistance) {
                closestDistance = distance;
                closestRow = row;
            }
        });

        if (closestRow) {
            targetRow = closestRow;
        }
    }

    // Perform the drop
    if (targetRow && targetRow !== touchDraggedGroupRow) {
        const tbody = document.getElementById('expense-groups-tbody');
        const allRows = Array.from(tbody.querySelectorAll('tr.draggable-row'));

        const draggedIndex = allRows.indexOf(touchDraggedGroupRow);
        const targetIndex = allRows.indexOf(targetRow);

        // Move the row
        if (deltaY > 0) {
            // Dragging down - insert after target
            targetRow.parentNode.insertBefore(touchDraggedGroupRow, targetRow.nextSibling);
        } else {
            // Dragging up - insert before target
            targetRow.parentNode.insertBefore(touchDraggedGroupRow, targetRow);
        }

        // Save new order to backend
        saveGroupsOrder();
    }

    // Reset visual feedback
    touchDraggedGroupRow.style.opacity = '1';
    touchDraggedGroupRow.style.transform = '';
    touchDraggedGroupRow.classList.remove('dragging');

    // Re-enable pointer events on all rows
    document.querySelectorAll('tr.draggable-row').forEach(r => {
        r.style.pointerEvents = '';
    });

    // Remove all highlights
    document.querySelectorAll('tr.draggable-row').forEach(r => {
        r.classList.remove('border-t-2', 'border-primary', 'border-b-2');
    });

    // Reset variables
    touchDraggedGroupRow = null;
    touchStartYGroups = 0;
    touchCurrentYGroups = 0;
}

function handleDragStart(e) {
    draggedRow = this;
    this.style.opacity = '0.4';
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', this.innerHTML);
}

function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleDragEnter(e) {
    if (this !== draggedRow) {
        this.classList.add('border-t-2', 'border-primary');
        draggedOverRow = this;
    }
}

function handleDragLeave(e) {
    this.classList.remove('border-t-2', 'border-primary');
}

function handleDrop(e) {
    if (e.stopPropagation) {
        e.stopPropagation();
    }
    
    if (draggedRow !== this) {
        // Get the tbody
        const tbody = document.getElementById('expense-groups-tbody');
        const allRows = Array.from(tbody.querySelectorAll('tr.draggable-row'));
        
        const draggedIndex = allRows.indexOf(draggedRow);
        const targetIndex = allRows.indexOf(this);
        
        // Move the dragged row
        if (draggedIndex < targetIndex) {
            this.parentNode.insertBefore(draggedRow, this.nextSibling);
        } else {
            this.parentNode.insertBefore(draggedRow, this);
        }
        
        // Save new order to backend
        saveGroupsOrder();
    }
    
    return false;
}

function handleDragEnd(e) {
    this.style.opacity = '1';
    
    // Remove all drag-related classes
    const rows = document.querySelectorAll('tr.draggable-row');
    rows.forEach(row => {
        row.classList.remove('border-t-2', 'border-primary');
    });
    
    draggedRow = null;
    draggedOverRow = null;
}

function saveGroupsOrder() {
    const tbody = document.getElementById('expense-groups-tbody');
    const rows = tbody.querySelectorAll('tr.draggable-row');
    
    const orderData = [];
    rows.forEach((row, index) => {
        const groupId = row.getAttribute('data-group-id');
        orderData.push({
            id: groupId,
            order: index + 1
        });
    });
    
    fetch(window.DASHBOARD_CONFIG.urls.reorderFlowgroups, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ groups: orderData })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            console.log('Order saved successfully');
            // Optionally update pie chart if order affects display
            updatePieChart();
        } else {
            console.error('Error saving order:', data.error);
            alert('window.DASHBOARD_CONFIG.i18n.errorSavingOrder ' + data.error);
        }
    })
    .catch(error => {
        console.error('Fetch Error:', error);
        alert('window.DASHBOARD_CONFIG.i18n.networkErrorOrder');
    });
}

// ========== DRAG AND DROP FOR INCOME ITEMS ========== 
let draggedIncomeRow = null;
let draggedOverIncomeRow = null;

function initializeDragAndDropIncome() {
    const tbody = document.getElementById('income-items-body');
    if (!tbody) return;

    const rows = tbody.querySelectorAll('tr.swipeable-row-income');

    rows.forEach(row => {
        row.addEventListener('dragstart', handleDragStartIncome);
        row.addEventListener('dragover', handleDragOverIncome);
        row.addEventListener('dragenter', handleDragEnterIncome);
        row.addEventListener('dragleave', handleDragLeaveIncome);
        row.addEventListener('drop', handleDropIncome);
        row.addEventListener('dragend', handleDragEndIncome);
    });

    // Enable drag only from drag handle
    const dragHandles = tbody.querySelectorAll('.drag-handle-income');
    dragHandles.forEach(handle => {
        handle.addEventListener('mousedown', function(e) {
            const row = this.closest('tr');
            if (row && row.dataset.mode !== 'edit') {
                row.setAttribute('draggable', 'true');
            }
        });

        // CORREÇÃO: Touch support for mobile drag
        handle.addEventListener('touchstart', function(e) {
            const row = this.closest('tr');
            if (row && row.dataset.mode !== 'edit') {
                row.setAttribute('draggable', 'true');
                handleTouchDragStartIncome(e, row);
            }
        }, { passive: false });
    });

    // Disable dragging when not on handle or in edit mode
    rows.forEach(row => {
        row.addEventListener('mousedown', function(e) {
            if (this.dataset.mode === 'edit' ||
                (!e.target.closest('.drag-handle-cell-income') && !e.target.closest('.drag-handle-income'))) {
                this.setAttribute('draggable', 'false');
            } else {
                this.setAttribute('draggable', 'true');
            }
        });

        // CORREÇÃO: Adicionar touch event listeners para mobile
        row.addEventListener('touchmove', handleTouchDragMoveIncome, { passive: false });
        row.addEventListener('touchend', handleTouchDragEndIncome, { passive: false });
    });
}

// CORREÇÃO: Variáveis para mobile drag de income
let touchDraggedIncomeRow = null;
let touchStartYIncome = 0;
let touchCurrentYIncome = 0;

function handleTouchDragStartIncome(e, row) {
    // Ignore if in edit mode or not on drag handle
    if (row.dataset.mode === 'edit') return;
    if (!e.target.closest('.drag-handle-income')) return;

    e.preventDefault();
    touchDraggedIncomeRow = row;
    touchStartYIncome = e.touches[0].clientY;
    touchCurrentYIncome = touchStartYIncome;

    // Visual feedback
    row.style.opacity = '0.4';
    row.classList.add('dragging');

    // Disable pointer events on other rows to prevent conflicts
    document.querySelectorAll('tr.swipeable-row-income').forEach(r => {
        if (r !== row) {
            r.style.pointerEvents = 'none';
        }
    });
}

function handleTouchDragMoveIncome(e) {
    if (!touchDraggedIncomeRow) return;
    if (this !== touchDraggedIncomeRow) return;

    e.preventDefault();
    touchCurrentYIncome = e.touches[0].clientY;

    const deltaY = touchCurrentYIncome - touchStartYIncome;

    // Find the row under the touch point
    const elementBelow = document.elementFromPoint(
        e.touches[0].clientX,
        e.touches[0].clientY
    );

    const rowBelow = elementBelow ? elementBelow.closest('tr.swipeable-row-income') : null;

    // Remove previous highlights
    document.querySelectorAll('tr.swipeable-row-income').forEach(r => {
        r.classList.remove('border-t-2', 'border-primary', 'border-b-2');
    });

    // Highlight the target row
    if (rowBelow && rowBelow !== touchDraggedIncomeRow && rowBelow.id !== 'new-income-template') {
        if (deltaY > 0) {
            // Dragging down
            rowBelow.classList.add('border-b-2', 'border-primary');
        } else {
            // Dragging up
            rowBelow.classList.add('border-t-2', 'border-primary');
        }
    }

    // Visual feedback - move the row
    touchDraggedIncomeRow.style.transform = `translateY(${deltaY}px)`;
}

function handleTouchDragEndIncome(e) {
    if (!touchDraggedIncomeRow) return;
    if (this !== touchDraggedIncomeRow) return;

    e.preventDefault();

    const deltaY = touchCurrentYIncome - touchStartYIncome;

    const rect = touchDraggedIncomeRow.getBoundingClientRect();
    const centerX = rect.left + (rect.width / 2);

    touchDraggedIncomeRow.style.visibility = 'hidden';
    const elementBelow = document.elementFromPoint(centerX, touchCurrentYIncome);
    touchDraggedIncomeRow.style.visibility = '';

    let targetRow = elementBelow ? elementBelow.closest('tr.swipeable-row-income') : null;

    if (!targetRow) {
        const tbody = document.getElementById('income-items-body');
        const allRows = Array.from(tbody.querySelectorAll('tr.swipeable-row-income:not(#new-income-template)'));

        let closestRow = null;
        let closestDistance = Infinity;

        allRows.forEach(function(row) {
            if (row === touchDraggedIncomeRow) return;

            const rowRect = row.getBoundingClientRect();
            const rowCenterY = rowRect.top + (rowRect.height / 2);
            const distance = Math.abs(touchCurrentYIncome - rowCenterY);

            if (distance < closestDistance) {
                closestDistance = distance;
                closestRow = row;
            }
        });

        if (closestRow) {
            targetRow = closestRow;
        }
    }

    // Perform the drop
    if (targetRow && targetRow !== touchDraggedIncomeRow && targetRow.id !== 'new-income-template') {
        const tbody = document.getElementById('income-items-body');
        const allRows = Array.from(tbody.querySelectorAll('tr.swipeable-row-income'));

        const draggedIndex = allRows.indexOf(touchDraggedIncomeRow);
        const targetIndex = allRows.indexOf(targetRow);

        // Move the row
        if (deltaY > 0) {
            // Dragging down - insert after target
            targetRow.parentNode.insertBefore(touchDraggedIncomeRow, targetRow.nextSibling);
        } else {
            // Dragging up - insert before target
            targetRow.parentNode.insertBefore(touchDraggedIncomeRow, targetRow);
        }

        // Save new order to backend
        saveIncomeItemsOrder();
    }

    // Reset visual feedback
    touchDraggedIncomeRow.style.opacity = '1';
    touchDraggedIncomeRow.style.transform = '';
    touchDraggedIncomeRow.classList.remove('dragging');

    // Re-enable pointer events on all rows
    document.querySelectorAll('tr.swipeable-row-income').forEach(r => {
        r.style.pointerEvents = '';
    });

    // Remove all highlights
    document.querySelectorAll('tr.swipeable-row-income').forEach(r => {
        r.classList.remove('border-t-2', 'border-primary', 'border-b-2');
    });

    // Reset variables
    touchDraggedIncomeRow = null;
    touchStartYIncome = 0;
    touchCurrentYIncome = 0;
}

function handleDragStartIncome(e) {
    draggedIncomeRow = this;
    this.style.opacity = '0.4';
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', this.innerHTML);
}

function handleDragOverIncome(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleDragEnterIncome(e) {
    if (this !== draggedIncomeRow) {
        this.classList.add('border-t-2', 'border-primary');
        draggedOverIncomeRow = this;
    }
}

function handleDragLeaveIncome(e) {
    this.classList.remove('border-t-2', 'border-primary');
}

function handleDropIncome(e) {
    if (e.stopPropagation) {
        e.stopPropagation();
    }

    if (draggedIncomeRow !== this) {
        const tbody = document.getElementById('income-items-body');
        const allRows = Array.from(tbody.querySelectorAll('tr.swipeable-row-income'));

        const draggedIndex = allRows.indexOf(draggedIncomeRow);
        const targetIndex = allRows.indexOf(this);

        // Move the dragged row
        if (draggedIndex < targetIndex) {
            this.parentNode.insertBefore(draggedIncomeRow, this.nextSibling);
        } else {
            this.parentNode.insertBefore(draggedIncomeRow, this);
        }

        // Save new order to backend
        saveIncomeItemsOrder();
    }

    return false;
}

function handleDragEndIncome(e) {
    this.style.opacity = '1';

    // Remove all drag-related classes
    const rows = document.querySelectorAll('tr.swipeable-row-income');
    rows.forEach(row => {
        row.classList.remove('border-t-2', 'border-primary');
    });

    draggedIncomeRow = null;
    draggedOverIncomeRow = null;
}

function saveIncomeItemsOrder() {
    const tbody = document.getElementById('income-items-body');
    const rows = tbody.querySelectorAll('tr.swipeable-row-income');

    const orderData = [];
    rows.forEach((row, index) => {
        // CORREÇÃO: Ignorar template row (new-income-template ou qualquer id que não comece com income-item-)
        if (!row.id.startsWith('income-item-')) {
            return;
        }
        const itemId = row.id.replace('income-item-', '');
        if (itemId && itemId !== 'NEW' && !isNaN(itemId)) {
            orderData.push({
                id: parseInt(itemId),
                order: index + 1
            });
        }
    });

    fetch(window.DASHBOARD_CONFIG.urls.reorderIncome, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ items: orderData })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            console.log('Income order saved successfully');
        } else {
            console.error('Error saving income order:', data.error);
            alert('window.DASHBOARD_CONFIG.i18n.errorSavingOrder ' + data.error);
        }
    })
    .catch(error => {
        console.error('Fetch Error:', error);
        alert('window.DASHBOARD_CONFIG.i18n.networkErrorOrder');
    });
}

// ========== MOBILE-SPECIFIC FUNCTIONALITY FOR INCOME ==========
// Initialize mobile swipe and tap functionality for income items
function initMobileIncomeFeatures() {
    'use strict';

    const isMobile = window.matchMedia('(max-width: 768px)').matches;

    if (!isMobile) {
        console.log('[MOBILE INCOME] Not mobile viewport, skipping mobile features');
        return; // Only run on mobile devices
    }

    console.log('[MOBILE INCOME] Initializing mobile features for income items');
    const swipeableRows = document.querySelectorAll('.swipeable-row-income');
    console.log('[MOBILE INCOME] Found', swipeableRows.length, 'swipeable rows');

    swipeableRows.forEach(row => {
        // CRITICAL FIX: Skip if already initialized to avoid duplicate listeners
        if (row.dataset.mobileInitialized === 'true') {
            return;
        }
        row.dataset.mobileInitialized = 'true';


        let startX = 0;
        let currentX = 0;
        let isDragging = false;
        let startTime = 0;
        const swipeThreshold = 60; // Minimum pixels to trigger swipe
        const tapTimeThreshold = 200; // Max ms for tap detection

        // CORREÇÃO: Variáveis para detectar drag vertical vs swipe horizontal
        let startY = 0;
        let currentY = 0;
        let isDragMode = false; // true = vertical drag, false = horizontal swipe
        let isDecided = false; // se já decidimos o modo

        // Touch start
        row.addEventListener('touchstart', (e) => {
            // CORREÇÃO: Se começou no drag handle, NÃO processar swipe
            const isDragHandle = e.target.closest('.drag-handle-income');
            if (isDragHandle) {
                // Drag handle vai cuidar, não processar swipe aqui
                return;
            }

            // Ignore if touching action buttons or check icon
            if (e.target.closest('.mobile-action-btn-income')) return;
            if (e.target.closest('.edit-save-icon-income')) return;

            startX = e.touches[0].clientX;
            currentX = startX;
            startY = e.touches[0].clientY;
            currentY = startY;
            startTime = Date.now();
            isDragging = false;
            isDecided = false;
            isDragMode = false;
        }, { passive: true });

        // Touch move
        row.addEventListener('touchmove', (e) => {
            // Se já decidiu que é drag, ignora swipe
            if (isDragMode) return;

            if (e.target.closest('.mobile-action-btn-income')) return;
            if (e.target.closest('.edit-save-icon-income')) return;

            currentX = e.touches[0].clientX;
            currentY = e.touches[0].clientY;
            const deltaX = currentX - startX;
            const deltaY = currentY - startY;

            // Processar apenas swipe horizontal
            // In edit mode: allow swipe right to cancel
            if (row.dataset.mode === 'edit') {
                if (deltaX > 0) {
                    isDragging = true;
                    const translateX = Math.min(deltaX, 120);
                    row.style.transform = `translateX(${translateX}px)`;
                    row.style.transition = 'none';
                }
            } else {
                // In display mode: allow swipe left to reveal actions
                if (deltaX < 0) {
                    isDragging = true;
                    const translateX = Math.max(deltaX, -120);
                    row.style.transform = `translateX(${translateX}px)`;
                    row.style.transition = 'none';
                }
            }
        }, { passive: true });

        // Touch end
        row.addEventListener('touchend', (e) => {
            // Se foi drag, não processar swipe
            if (isDragMode) return;

            const deltaX = currentX - startX;
            const deltaTime = Date.now() - startTime;
            row.style.transition = 'transform 0.3s ease-out';

            // In edit mode: swipe right to cancel
            if (row.dataset.mode === 'edit') {
                if (deltaX > swipeThreshold) {
                    console.log('[MOBILE INCOME SWIPE] Canceling edit mode for:', row.id);
                    // CRITICAL FIX: If it's the template, call cancelNewIncomeRow instead of toggleEditMode
                    if (row.id === 'new-income-template') {
                        window.cancelNewIncomeRow('new-income-template');
                    } else {
                        toggleEditMode(row.id, false);
                    }
                } else {
                    row.style.transform = 'translateX(0)';
                }
            } else {
                // CRITICAL FIX: If actions are revealed, tap should close swipe instead of toggling realized
                const hasActionsRevealed = row.classList.contains('actions-revealed-income');

                // Tap detection
                if (!isDragging && Math.abs(deltaX) < 10 && deltaTime < tapTimeThreshold) {
                    if (hasActionsRevealed) {
                        // Close swipe instead of toggling realized
                        console.log('[MOBILE INCOME TAP] Closing swipe for:', row.id);
                        row.style.transform = 'translateX(0)';
                        row.classList.remove('actions-revealed-income');
                        // CRITICAL FIX: Re-enable drag when returning to original position
                        row.setAttribute('draggable', 'true');
                    } else {
                        // Toggle realized only if no swipe revealed
                        const rowId = row.id;
                        console.log('[MOBILE INCOME TAP] Toggling realized:', rowId);
                        toggleIncomeRealized(rowId);
                    }
                }
                // Swipe left to reveal actions
                else if (deltaX < -swipeThreshold) {
                    row.style.transform = 'translateX(-120px)';
                    row.classList.add('actions-revealed-income');
                    // CRITICAL FIX: Disable drag when swipe is revealed
                    row.setAttribute('draggable', 'false');
                } else {
                    row.style.transform = 'translateX(0)';
                    row.classList.remove('actions-revealed-income');
                    // CRITICAL FIX: Re-enable drag when returning to original position
                    row.setAttribute('draggable', 'true');
                }
            }

            isDragging = false;
            isDecided = false;
            isDragMode = false;
        }, { passive: true });

        // Close actions when tapping outside
        document.addEventListener('touchstart', (e) => {
            if (!row.contains(e.target) && row.classList.contains('actions-revealed-income')) {
                row.style.transform = 'translateX(0)';
                row.classList.remove('actions-revealed-income');
                // CRITICAL FIX: Re-enable drag when returning to original position
                row.setAttribute('draggable', 'true');
            }
        }, { passive: true });
    });

    // Add change event listener to all income date inputs to update display value
    const dateInputs = document.querySelectorAll('.date-input-field-income');
    dateInputs.forEach(input => {
        // Set initial display value
        const dateValue = input.value; // YYYY-MM-DD format
        if (dateValue) {
            const [year, month, day] = dateValue.split('-');
            const displayValue = `${day}/${month}`;
            input.setAttribute('data-display-value', displayValue);
        }

        // Update display value when date changes
        input.addEventListener('change', function() {
            const dateValue = this.value; // YYYY-MM-DD format
            if (dateValue) {
                const [year, month, day] = dateValue.split('-');
                const displayValue = `${day}/${month}`;
                this.setAttribute('data-display-value', displayValue);
                console.log('[MOBILE INCOME DATE] Updated display value:', displayValue);
            }
        });
    });
}

// Initialize mobile features on page load
document.addEventListener('DOMContentLoaded', function() {
    initMobileIncomeFeatures();
});

// Expose function globally so it can be called after adding new rows
window.initMobileIncomeFeatures = initMobileIncomeFeatures;

// Note: normalizeDecimalInput function removed - backend now handles all locale parsing

// Mobile keyboard handling - scroll input into view when keyboard opens
function initMobileKeyboardHandling() {
    // Só executa em mobile
    if (window.innerWidth > 768) return;

    const inputs = document.querySelectorAll('input, select, textarea');

    inputs.forEach(input => {
        input.addEventListener('focus', function() {
            // Timeout para aguardar teclado aparecer
            setTimeout(() => {
                if (window.visualViewport) {
                    const keyboardHeight = window.innerHeight - window.visualViewport.height;

                    if (keyboardHeight > 50) { // Teclado está visível
                        this.scrollIntoView({
                            behavior: 'smooth',
                            block: 'center',
                            inline: 'nearest'
                        });
                    }
                } else {
                    // Fallback para browsers sem visualViewport API
                    this.scrollIntoView({
                        behavior: 'smooth',
                        block: 'center',
                        inline: 'nearest'
                    });
                }
            }, 300); // Aguarda 300ms para teclado aparecer
        });
    });
}

// ===== REALTIME UPDATES FOR YTD METRICS =====

/**
 * Update YTD Metrics via AJAX
 * Fetches fresh YTD Income, Savings, and Investments values from server
 */
function updateSummary() {
    console.log('[Dashboard YTD] updateSummary() called - fetching YTD metrics from server');

    const config = document.getElementById('dashboard-config');
    if (!config) {
        console.error('[Dashboard YTD] Configuration element not found!');
        return;
    }

    const ytdMetricsUrl = config.dataset.urlYtdMetrics;
    if (!ytdMetricsUrl) {
        console.error('[Dashboard YTD] YTD metrics URL not found in config!');
        return;
    }

    // Get current period from URL
    const urlParams = new URLSearchParams(window.location.search);
    const period = urlParams.get('period') || '';
    const url = ytdMetricsUrl + (period ? `?period=${period}` : '');

    console.log('[Dashboard YTD] Fetching from:', url);

    fetch(url, {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
        },
    })
    .then(response => {
        console.log('[Dashboard YTD] Response status:', response.status);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('[Dashboard YTD] Response data:', data);

        if (data.status === 'success') {
            const metrics = data.ytd_metrics;
            console.log('[Dashboard YTD] YTD metrics received:', metrics);

            // Format values with thousand separators
            const formatValue = (value) => {
                const num = parseFloat(value);
                if (isNaN(num)) return value;
                return num.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            };

            // Update YTD Income
            const ytdIncomeEl = document.getElementById('ytd-income-value');
            if (ytdIncomeEl) {
                ytdIncomeEl.textContent = `${metrics.currency_symbol} ${formatValue(metrics.ytd_income)}`;
                console.log('[Dashboard YTD] Updated YTD Income to:', ytdIncomeEl.textContent);
            } else {
                console.warn('[Dashboard YTD] ytd-income-value element not found');
            }

            // Update YTD Savings (with color logic)
            const ytdSavingsEl = document.getElementById('ytd-savings-value');
            if (ytdSavingsEl) {
                ytdSavingsEl.textContent = `${metrics.currency_symbol} ${formatValue(metrics.ytd_savings)}`;

                // Update color based on positive/negative
                const savingsValue = parseFloat(metrics.ytd_savings);
                ytdSavingsEl.classList.remove('text-green-600', 'dark:text-green-500', 'text-red-600', 'dark:text-red-500');
                if (savingsValue >= 0) {
                    ytdSavingsEl.classList.add('text-green-600', 'dark:text-green-500');
                } else {
                    ytdSavingsEl.classList.add('text-red-600', 'dark:text-red-500');
                }
                console.log('[Dashboard YTD] Updated YTD Savings to:', ytdSavingsEl.textContent);
            } else {
                console.warn('[Dashboard YTD] ytd-savings-value element not found');
            }

            console.log('[Dashboard YTD] YTD metrics updated successfully!');
        } else {
            console.error('[Dashboard YTD] Server returned error:', data.error);
        }
    })
    .catch(error => {
        console.error('[Dashboard YTD] Error fetching YTD metrics:', error);
    });
}

// Listen for income transaction events to update YTD metrics
document.addEventListener('realtime:transaction:created', function(event) {
    console.log('[Dashboard YTD] Transaction created event received:', event.detail);
    const data = event.detail.data;
    console.log('[Dashboard YTD] Transaction data:', data);
    console.log('[Dashboard YTD] is_income flag:', data.is_income);
    // Only update if it's an income transaction
    if (data.is_income) {
        console.log('[Dashboard YTD] Income created, calling updateSummary()');
        updateSummary();
    } else {
        console.log('[Dashboard YTD] Not an income transaction, skipping YTD update');
    }
});

document.addEventListener('realtime:transaction:updated', function(event) {
    console.log('[Dashboard YTD] Transaction updated event received:', event.detail);
    const data = event.detail.data;
    console.log('[Dashboard YTD] Transaction data:', data);
    console.log('[Dashboard YTD] is_income flag:', data.is_income);
    // Only update if it's an income transaction
    if (data.is_income) {
        console.log('[Dashboard YTD] Income updated, calling updateSummary()');
        updateSummary();
    } else {
        console.log('[Dashboard YTD] Not an income transaction, skipping YTD update');
    }
});

document.addEventListener('realtime:transaction:deleted', function(event) {
    console.log('[Dashboard YTD] Transaction deleted event received:', event.detail);
    const data = event.detail.data;
    console.log('[Dashboard YTD] Transaction data:', data);
    console.log('[Dashboard YTD] is_income flag:', data.is_income);
    // Only update if it's an income transaction
    if (data.is_income) {
        console.log('[Dashboard YTD] Income deleted, calling updateSummary()');
        updateSummary();
    } else {
        console.log('[Dashboard YTD] Not an income transaction, skipping YTD update');
    }
});

// Listen for balance updates (broadcasted after income realized status changes)
document.addEventListener('realtime:balance:updated', function(event) {
    console.log('[Dashboard YTD] Balance updated event received, calling updateSummary()');
    updateSummary();
});

// Inicializar quando DOM carregar
document.addEventListener('DOMContentLoaded', function() {
    initDashboard();
    initDragAndDrop();
});
