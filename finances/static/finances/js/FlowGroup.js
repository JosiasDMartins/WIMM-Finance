/**
 * FlowGroup.js - FlowGroup page functionality
 * PHASE 3 CSP Compliance: All inline scripts moved to external file
 * Version: 20251231-002 - Fixed money mask parameters
 */

document.addEventListener('DOMContentLoaded', function() {
    // CRITICAL: Register form submit handler FIRST, before anything else
    const flowGroupForm = document.getElementById('flow-group-form');
    if (flowGroupForm) {
        flowGroupForm.addEventListener('submit', function(event) {
            console.log('[FlowGroup CRITICAL] Form submit event triggered - PREVENTING ALL SUBMISSIONS');
            console.log('[FlowGroup CRITICAL] event.submitter:', event.submitter);
            console.log('[FlowGroup CRITICAL] event.submitter type:', event.submitter ? event.submitter.getAttribute('type') : 'null');

            // ALWAYS prevent default first
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            // Check if the submit was triggered by the main save button
            const submitButton = event.submitter;
            if (submitButton && submitButton.getAttribute('type') === 'submit') {
                console.log('[FlowGroup CRITICAL] Main save button clicked - allowing submission');

                // CRITICAL FIX: Convert budgeted_amount to correct format before submit
                // Use the same getRawValue logic inline (config may not be loaded yet)
                const budgetInput = flowGroupForm.querySelector('input[name="budgeted_amount"]');
                if (budgetInput && budgetInput.value) {
                    const configEl = document.getElementById('flowgroup-config');
                    const decimalSep = configEl ? configEl.dataset.decimalSeparator : ',';
                    const thousandSep = configEl ? configEl.dataset.thousandSeparator : '.';

                    let value = budgetInput.value;
                    // Remove thousand separators
                    const escapedSeparator = thousandSep.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                    value = value.replace(new RegExp(escapedSeparator, 'g'), '');
                    // Replace decimal separator with dot
                    value = value.replace(decimalSep, '.');
                    budgetInput.value = value;
                    console.log('[FlowGroup CRITICAL] Converted budget value to:', budgetInput.value);
                }

                // Only allow if it's the main save button
                // Remove this handler temporarily to allow submission
                flowGroupForm.removeEventListener('submit', arguments.callee);
                flowGroupForm.submit();
            } else {
                console.warn('[FlowGroup CRITICAL] Form submission BLOCKED - not from main save button');
            }

            return false;
        }, true); // Use capture phase
        console.log('[FlowGroup CRITICAL] Form submit handler registered in CAPTURE phase');
    }

    // Initialize configuration from data attributes
    initFlowGroup();
});

function initFlowGroup() {
    const config = document.getElementById('flowgroup-config');
    if (!config) {
        console.error('[FlowGroup] Config element not found');
        return;
    }

    // Store configuration globally
    window.FLOWGROUP_CONFIG = {
        decimalSeparator: config.dataset.decimalSeparator || ',',
        thousandSeparator: config.dataset.thousandSeparator || '.',
        currencySymbol: config.dataset.currencySymbol || '$',
        memberRoleForPeriod: config.dataset.memberRoleForPeriod || '',
        selectedPeriod: config.dataset.selectedPeriod || '',
        flowGroupId: config.dataset.flowGroupId || '',
        isCreditCard: config.dataset.isCreditCard === 'true',
        isClosed: config.dataset.isClosed === 'true',

        // URLs
        urls: {
            toggleKidsGroupRealized: config.dataset.urlToggleKidsGroupRealized,
            toggleFlowgroupRecurring: config.dataset.urlToggleFlowgroupRecurring,
            toggleCreditCardClosed: config.dataset.urlToggleCreditCardClosed,
            toggleTransactionFixed: config.dataset.urlToggleTransactionFixed,
            saveFlowItem: config.dataset.urlSaveFlowItem,
            deleteFlowItem: config.dataset.urlDeleteFlowItem,
            reorderFlowItems: config.dataset.urlReorderFlowItems,
            deleteFlowGroup: config.dataset.urlDeleteFlowGroup,
            dashboard: config.dataset.urlDashboard
        },

        // i18n strings
        i18n: {
            estimatedExpenses: config.dataset.i18nEstimatedExpenses,
            exceedBudget: config.dataset.i18nExceedBudget,
            markedAsGiven: config.dataset.i18nMarkedAsGiven,
            notGivenYet: config.dataset.i18nNotGivenYet,
            budgetMarkedAsGiven: config.dataset.i18nBudgetMarkedAsGiven,
            budgetMarkedAsNotGiven: config.dataset.i18nBudgetMarkedAsNotGiven,
            errorUpdatingStatus: config.dataset.i18nErrorUpdatingStatus,
            networkError: config.dataset.i18nNetworkError,
            groupMarkedRecurring: config.dataset.i18nGroupMarkedRecurring,
            groupNotRecurring: config.dataset.i18nGroupNotRecurring,
            errorUpdatingRecurring: config.dataset.i18nErrorUpdatingRecurring,
            billClosed: config.dataset.i18nBillClosed,
            billMarkedClosed: config.dataset.i18nBillMarkedClosed,
            billMarkedNotClosed: config.dataset.i18nBillMarkedNotClosed,
            billOpen: config.dataset.i18nBillOpen,
            itemsMarkedRealized: config.dataset.i18nItemsMarkedRealized,
            pleaseSaveFlowGroupBeforeClosed: config.dataset.i18nPleaseSaveFlowGroupBeforeClosed,
            pleaseSaveFlowGroupBeforeRealized: config.dataset.i18nPleaseSaveFlowGroupBeforeRealized,
            pleaseSaveFlowGroupBeforeRecurring: config.dataset.i18nPleaseSaveFlowGroupBeforeRecurring,
            pleaseSaveTransactionBeforeFixed: config.dataset.i18nPleaseSaveTransactionBeforeFixed,
            realized: config.dataset.i18nRealized,
            notRealized: config.dataset.i18nNotRealized,
            recurring: config.dataset.i18nRecurring,
            notRecurring: config.dataset.i18nNotRecurring,
            transactionMarkedFixed: config.dataset.i18nTransactionMarkedFixed,
            transactionNotFixed: config.dataset.i18nTransactionNotFixed,
            deletionWarning: config.dataset.i18nDeletionWarning,
            confirmDelete: config.dataset.i18nConfirmDelete,
            flowGroupDeleted: config.dataset.i18nFlowGroupDeleted,
            errorDeletingFlowGroup: config.dataset.i18nErrorDeletingFlowGroup,
            confirmDeleteItem: config.dataset.i18nConfirmDeleteItem,
            descriptionAmountDateRequired: config.dataset.i18nDescriptionAmountDateRequired,
            duplicateName: config.dataset.i18nDuplicateName,
            anotherUser: config.dataset.i18nAnotherUser,
            flowGroupDeletedByUser: config.dataset.i18nFlowGroupDeletedByUser,
            flowGroupDeletedTitle: config.dataset.i18nFlowGroupDeletedTitle,
            flowGroupDeletedSuccess: config.dataset.i18nFlowGroupDeletedSuccess,
            ok: config.dataset.i18nOk,
            networkErrorSavingOrder: config.dataset.i18nNetworkErrorSavingOrder
        }
    };

    // Get CSRF token
    const csrftoken = getCookie('csrftoken');
    window.FLOWGROUP_CSRF = csrftoken;

    // Initialize event listeners
    initCheckboxHandlers();
    initializeDragAndDrop();
    initializeNewItemToggle();

    // Check if bill is closed and block fields accordingly
    if (window.FLOWGROUP_CONFIG.isCreditCard && window.FLOWGROUP_CONFIG.isClosed) {
        blockAllFields(true);
        console.log('[DOMContentLoaded] Bill is closed, fields blocked');
    }

    // Add money mask to all amount fields using event delegation
    document.addEventListener('input', function(event) {
        if (event.target.matches('input[data-field="amount"]')) {
            applyMoneyMask(event, window.FLOWGROUP_CONFIG.thousandSeparator, window.FLOWGROUP_CONFIG.decimalSeparator);
        }
    });

    // Cursor positioned to the right only on first click/focus
    document.addEventListener('focus', function(event) {
        if (event.target.matches('input[data-field="amount"]')) {
            if (!event.target.hasAttribute('data-first-focus-done')) {
                event.target.setAttribute('data-first-focus-done', 'true');
                setTimeout(function() {
                    event.target.setSelectionRange(event.target.value.length, event.target.value.length);
                }, 0);
            }
        }
    }, true);

    // Reset flags when field loses focus
    document.addEventListener('blur', function(event) {
        if (event.target.matches('input[data-field="amount"]')) {
            event.target.removeAttribute('data-first-focus-done');
        }
    }, true);

    // Initialize existing amount fields with money mask on page load
    document.querySelectorAll('input[data-field="amount"]').forEach(function(input) {
        if (input.value && input.value.trim() !== '') {
            let value = input.value.replace(',', '.');
            let num = parseFloat(value);
            if (!isNaN(num)) {
                let cents = Math.round(num * 100);
                let integerPart = Math.floor(cents / 100).toString();
                let decimalPart = (cents % 100).toString().padStart(2, '0');
                integerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, window.FLOWGROUP_CONFIG.thousandSeparator);
                input.value = integerPart + window.FLOWGROUP_CONFIG.decimalSeparator + decimalPart;
            } else {
                input.value = '0' + window.FLOWGROUP_CONFIG.decimalSeparator + '00';
            }
        } else {
            input.value = '0' + window.FLOWGROUP_CONFIG.decimalSeparator + '00';
        }
    });

    // Prevent Enter key from submitting form in item input fields
    const flowGroupForm = document.getElementById('flow-group-form');
    if (flowGroupForm) {
        flowGroupForm.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                const target = event.target;
                // Check if Enter was pressed in an item input field (not in the main form fields)
                if (target.matches('input[data-field], select[data-field]')) {
                    console.log('[FlowGroup] Enter key pressed in item field, preventing form submission');
                    event.preventDefault();
                    return false;
                }
            }
        });
    }

    // Event delegation for data-action buttons
    document.addEventListener('click', function(event) {
        const button = event.target.closest('[data-action]');
        if (!button) return;

        const action = button.getAttribute('data-action');
        const rowId = button.getAttribute('data-row-id') || button.getAttribute('data-item-id');

        console.log('[Event Delegation] Action:', action, 'RowId:', rowId);

        switch (action) {
            case 'add-new-row':
                event.preventDefault();
                window.addNewRow();
                break;
            case 'cancel-new-row':
                event.preventDefault();
                window.cancelNewRow(rowId);
                break;
            case 'save':
                event.preventDefault();
                window.saveItem(rowId);
                break;
            case 'cancel':
                event.preventDefault();
                window.cancelEdit(rowId);
                break;
            case 'edit':
                event.preventDefault();
                window.toggleEditMode(rowId);
                break;
            case 'delete':
                event.preventDefault();
                window.deleteItem(rowId);
                break;
            case 'toggle-transaction-fixed':
                event.preventDefault();
                window.toggleTransactionFixed(rowId);
                break;
            case 'toggle-new-item-fixed':
                event.preventDefault();
                window.toggleNewItemFixed();
                break;
        }
    });
}

// Utility for getting CSRF token
// getCookie - using utils.js

// Handle Kids checkbox change
function handleKidsChange() {
    const kidsCheckbox = document.getElementById('id_is_kids_group');
    const sharedCheckbox = document.getElementById('id_is_shared');
    const childrenContainer = document.getElementById('children-selection-container');
    const membersContainer = document.getElementById('members-selection-container');

    if (kidsCheckbox.checked) {
        sharedCheckbox.checked = true;
        sharedCheckbox.disabled = true;
        childrenContainer.style.display = 'flex';
        membersContainer.style.display = 'none';
    } else {
        sharedCheckbox.disabled = false;
        childrenContainer.style.display = 'none';
        if (sharedCheckbox.checked) {
            membersContainer.style.display = 'flex';
        }
    }
}

// Handle Shared checkbox change
function handleSharedChange() {
    const sharedCheckbox = document.getElementById('id_is_shared');
    const kidsCheckbox = document.getElementById('id_is_kids_group');
    const membersContainer = document.getElementById('members-selection-container');

    if (sharedCheckbox.checked && !kidsCheckbox.checked) {
        membersContainer.style.display = 'flex';
    } else {
        membersContainer.style.display = 'none';
    }
}

// Handle Credit Card checkbox change
function handleCreditCardChange() {
    // Currently no special handling needed on checkbox change
}

function initCheckboxHandlers() {
    const kidsCheckbox = document.getElementById('id_is_kids_group');
    const sharedCheckbox = document.getElementById('id_is_shared');
    const creditCardCheckbox = document.getElementById('id_is_credit_card');

    if (kidsCheckbox) {
        kidsCheckbox.addEventListener('change', handleKidsChange);
        handleKidsChange(); // Initialize on page load
    }

    if (sharedCheckbox) {
        sharedCheckbox.addEventListener('change', handleSharedChange);
    }

    if (creditCardCheckbox) {
        creditCardCheckbox.addEventListener('change', handleCreditCardChange);
    }
}

// Function to toggle Kids Group realized status (Parents/Admins only)
window.toggleKidsGroupRealized = function(currentStatus) {
    const flowGroupId = document.getElementById('flow-group-form').getAttribute('data-flow-group-id');

    if (flowGroupId === 'NEW') {
        alert(window.FLOWGROUP_CONFIG.i18n.pleaseSaveFlowGroupBeforeRealized);
        return;
    }

    const newStatus = !currentStatus;

    fetch(window.FLOWGROUP_CONFIG.urls.toggleKidsGroupRealized, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.FLOWGROUP_CSRF,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({
            'flow_group_id': flowGroupId,
            'realized': newStatus
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            const toggleBtn = document.querySelector('.kids-group-realized-toggle');
            const toggleCircle = toggleBtn.querySelector('span');
            const statusText = toggleBtn.parentElement.querySelector('.text-xs');

            if (data.realized) {
                toggleBtn.classList.remove('bg-gray-300', 'dark:bg-gray-600');
                toggleBtn.classList.add('bg-green-500');
                toggleCircle.classList.add('translate-x-5');
                statusText.textContent = window.FLOWGROUP_CONFIG.i18n.markedAsGiven;
                toggleBtn.setAttribute('data-action', 'toggle-kids-realized');
                toggleBtn.setAttribute('data-current-state', 'true');
            } else {
                toggleBtn.classList.remove('bg-green-500');
                toggleBtn.classList.add('bg-gray-300', 'dark:bg-gray-600');
                toggleCircle.classList.remove('translate-x-5');
                statusText.textContent = window.FLOWGROUP_CONFIG.i18n.notGivenYet;
                toggleBtn.setAttribute('data-action', 'toggle-kids-realized');
                toggleBtn.setAttribute('data-current-state', 'false');
            }

            showSuccessMessage(data.realized ? window.FLOWGROUP_CONFIG.i18n.budgetMarkedAsGiven : window.FLOWGROUP_CONFIG.i18n.budgetMarkedAsNotGiven);
        } else {
            alert(window.FLOWGROUP_CONFIG.i18n.errorUpdatingStatus + ' ' + data.error);
        }
    })
    .catch(error => {
        console.error('Fetch Error:', error);
        alert(window.FLOWGROUP_CONFIG.i18n.networkError);
    });
};

// Function to toggle FlowGroup recurring status (Parents/Admins only)
window.toggleFlowGroupRecurring = function() {
    const flowGroupId = document.getElementById('flow-group-form').getAttribute('data-flow-group-id');

    if (flowGroupId === 'NEW') {
        alert(window.FLOWGROUP_CONFIG.i18n.pleaseSaveFlowGroupBeforeRecurring);
        return;
    }

    fetch(window.FLOWGROUP_CONFIG.urls.toggleFlowgroupRecurring, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.FLOWGROUP_CSRF,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({
            'flow_group_id': flowGroupId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            const recurringBtn = document.getElementById('recurring-btn');
            const recurringBtnMobile = document.getElementById('recurring-btn-mobile');

            if (recurringBtn) {
                const iconContainer = recurringBtn.querySelector('span:last-child');
                if (data.is_recurring) {
                    recurringBtn.classList.remove('bg-blue-600/30', 'text-blue-600', 'dark:text-blue-400', 'hover:bg-blue-600/50');
                    recurringBtn.classList.add('bg-blue-600', 'text-white', 'hover:bg-blue-700');
                    iconContainer.classList.remove('bg-blue-700/50');
                    iconContainer.classList.add('bg-blue-800');
                } else {
                    recurringBtn.classList.remove('bg-blue-600', 'text-white', 'hover:bg-blue-700');
                    recurringBtn.classList.add('bg-blue-600/30', 'text-blue-600', 'dark:text-blue-400', 'hover:bg-blue-600/50');
                    iconContainer.classList.remove('bg-blue-800');
                    iconContainer.classList.add('bg-blue-700/50');
                }
            }

            if (recurringBtnMobile) {
                const iconContainerMobile = recurringBtnMobile.querySelector('span:last-child');
                if (data.is_recurring) {
                    recurringBtnMobile.classList.remove('bg-blue-600/30', 'text-blue-600', 'dark:text-blue-400', 'hover:bg-blue-600/50');
                    recurringBtnMobile.classList.add('bg-blue-600', 'text-white', 'hover:bg-blue-700');
                    iconContainerMobile.classList.remove('bg-blue-700/50');
                    iconContainerMobile.classList.add('bg-blue-800');
                } else {
                    recurringBtnMobile.classList.remove('bg-blue-600', 'text-white', 'hover:bg-blue-700');
                    recurringBtnMobile.classList.add('bg-blue-600/30', 'text-blue-600', 'dark:text-blue-400', 'hover:bg-blue-600/50');
                    iconContainerMobile.classList.remove('bg-blue-800');
                    iconContainerMobile.classList.add('bg-blue-700/50');
                }
            }

            showSuccessMessage(data.is_recurring ? window.FLOWGROUP_CONFIG.i18n.groupMarkedRecurring : window.FLOWGROUP_CONFIG.i18n.groupNotRecurring);
        } else {
            alert(window.FLOWGROUP_CONFIG.i18n.errorUpdatingRecurring + ' ' + data.error);
        }
    })
    .catch(error => {
        console.error('Fetch Error:', error);
        alert(window.FLOWGROUP_CONFIG.i18n.networkError);
    });
};

// Function to toggle Credit Card closed status (Parents/Admins only)
window.toggleCreditCardClosed = function(currentStatus) {
    const flowGroupId = document.getElementById('flow-group-form').getAttribute('data-flow-group-id');

    if (flowGroupId === 'NEW') {
        alert(window.FLOWGROUP_CONFIG.i18n.pleaseSaveFlowGroupBeforeClosed);
        return;
    }

    const newStatus = !currentStatus;

    fetch(window.FLOWGROUP_CONFIG.urls.toggleCreditCardClosed, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.FLOWGROUP_CSRF,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({
            'flow_group_id': flowGroupId,
            'closed': newStatus
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            const closedBtn = document.getElementById('closed-btn');
            const closedBtnMobile = document.getElementById('closed-btn-mobile');

            if (data.closed) {
                if (closedBtn) {
                    const iconContainer = closedBtn.querySelector('span:last-child');
                    closedBtn.style.backgroundColor = '#dc2626';
                    closedBtn.style.color = 'white';
                    closedBtn.style.border = 'none';
                    iconContainer.style.backgroundColor = '#991b1b';
                    closedBtn.setAttribute('data-action', 'toggle-creditcard-closed');
                    closedBtn.setAttribute('data-current-state', 'true');
                }

                if (closedBtnMobile) {
                    const iconContainerMobile = closedBtnMobile.querySelector('span:last-child');
                    closedBtnMobile.style.backgroundColor = '#dc2626';
                    closedBtnMobile.style.color = 'white';
                    closedBtnMobile.style.border = 'none';
                    iconContainerMobile.style.backgroundColor = '#991b1b';
                    closedBtnMobile.setAttribute('data-action', 'toggle-creditcard-closed');
                    closedBtnMobile.setAttribute('data-current-state', 'true');
                }

                // Update all transaction toggles to realized=true
                const tbody = document.getElementById('expense-items-body');
                console.log('[Credit Card Toggle] Looking for tbody:', tbody);
                if (tbody) {
                    const rows = tbody.querySelectorAll('tr[id^="item-"]');
                    console.log('[Credit Card Toggle] Found rows:', rows.length);
                    rows.forEach(row => {
                        const itemId = row.id.replace('item-', '');
                        console.log('[Credit Card Toggle] Processing item:', itemId);
                        if (itemId !== 'NEW') {
                            row.setAttribute('data-realized', 'true');

                            const itemToggle = row.querySelector('.realized-toggle');
                            console.log('[Credit Card Toggle] Found toggle for item', itemId, ':', itemToggle);
                            if (itemToggle) {
                                const itemToggleCircle = itemToggle.querySelector('span');
                                console.log('[Credit Card Toggle] Found toggle circle:', itemToggleCircle);

                                itemToggle.classList.remove('bg-gray-300', 'dark:bg-gray-600');
                                itemToggle.classList.add('bg-green-500');

                                if (itemToggleCircle) {
                                    itemToggleCircle.classList.add('translate-x-4');
                                }

                                itemToggle.setAttribute('data-toggle', 'realized');
                                itemToggle.setAttribute('data-item-id', 'item-' + itemId);
                                itemToggle.setAttribute('data-current-state', 'true');
                            }

                            row.classList.remove('row-not-realized');
                            row.classList.add('row-realized');
                        }
                    });
                } else {
                    console.error('[Credit Card Toggle] tbody not found!');
                }

                // Update budget field with actual total from backend
                const budgetInput = document.querySelector('input[name="budgeted_amount"]');
                if (budgetInput && data.budget) {
                    budgetInput.value = data.budget;
                    console.log('[Credit Card Toggle] Updated budget to:', data.budget);
                }

                // Update summary section
                updateSummary(data.budget, data.total_realized);

                // Block all fields
                blockAllFields(true);

                showSuccessMessage(window.FLOWGROUP_CONFIG.i18n.billMarkedClosed + ' - ' + data.total_items + ' ' + window.FLOWGROUP_CONFIG.i18n.itemsMarkedRealized);
            } else {
                if (closedBtn) {
                    const iconContainer = closedBtn.querySelector('span:last-child');
                    closedBtn.style.backgroundColor = '';
                    closedBtn.style.color = '';
                    closedBtn.style.border = '';
                    iconContainer.style.backgroundColor = '';
                    closedBtn.setAttribute('data-action', 'toggle-creditcard-closed');
                    closedBtn.setAttribute('data-current-state', 'false');
                }

                if (closedBtnMobile) {
                    const iconContainerMobile = closedBtnMobile.querySelector('span:last-child');
                    closedBtnMobile.style.backgroundColor = '';
                    closedBtnMobile.style.color = '';
                    closedBtnMobile.style.border = '';
                    iconContainerMobile.style.backgroundColor = '';
                    closedBtnMobile.setAttribute('data-action', 'toggle-creditcard-closed');
                    closedBtnMobile.setAttribute('data-current-state', 'false');
                }

                // Unblock all fields
                blockAllFields(false);

                showSuccessMessage(window.FLOWGROUP_CONFIG.i18n.billMarkedNotClosed);
            }
        } else {
            alert(window.FLOWGROUP_CONFIG.i18n.errorUpdatingStatus + ' ' + data.error);
        }
    })
    .catch(error => {
        console.error('Fetch Error:', error);
        alert(window.FLOWGROUP_CONFIG.i18n.networkError);
    });
};

// Function to block/unblock all fields when bill is closed/opened
function blockAllFields(shouldBlock) {
    console.log('[Block Fields] shouldBlock:', shouldBlock);

    const budgetInput = document.querySelector('input[name="budgeted_amount"]');
    if (budgetInput) {
        budgetInput.disabled = shouldBlock;
        if (shouldBlock) {
            budgetInput.style.backgroundColor = '#f3f4f6';
            budgetInput.style.color = '#9ca3af';
            budgetInput.style.cursor = 'not-allowed';
        } else {
            budgetInput.style.backgroundColor = '';
            budgetInput.style.color = '';
            budgetInput.style.cursor = '';
        }
    }

    const nameInput = document.querySelector('input[name="name"]');
    if (nameInput) {
        nameInput.disabled = shouldBlock;
        if (shouldBlock) {
            nameInput.style.backgroundColor = '#f3f4f6';
            nameInput.style.color = '#9ca3af';
            nameInput.style.cursor = 'not-allowed';
        } else {
            nameInput.style.backgroundColor = '';
            nameInput.style.color = '';
            nameInput.style.cursor = '';
        }
    }

    const tbody = document.getElementById('expense-items-body');
    if (tbody) {
        const rows = tbody.querySelectorAll('tr[id^="item-"]');
        console.log('[Block Fields] Found rows:', rows.length);

        rows.forEach(row => {
            const itemId = row.id.replace('item-', '');
            if (itemId !== 'NEW' && itemId !== 'new-item-template') {
                console.log('[Block Fields] Processing row:', itemId);

                const allInputs = row.querySelectorAll('input, select');
                allInputs.forEach(input => {
                    input.disabled = shouldBlock;
                    if (shouldBlock) {
                        input.style.backgroundColor = '#f3f4f6';
                        input.style.color = '#9ca3af';
                        input.style.cursor = 'not-allowed';
                        input.style.opacity = '0.6';
                    } else {
                        input.style.backgroundColor = '';
                        input.style.color = '';
                        input.style.cursor = '';
                        input.style.opacity = '';
                    }
                });

                const realizedToggle = row.querySelector('.realized-toggle');
                if (realizedToggle) {
                    if (shouldBlock) {
                        realizedToggle.style.opacity = '0.4';
                        realizedToggle.style.cursor = 'not-allowed';
                        realizedToggle.style.pointerEvents = 'none';
                    } else {
                        realizedToggle.style.opacity = '';
                        realizedToggle.style.cursor = 'pointer';
                        realizedToggle.style.pointerEvents = '';
                    }
                }

                const fixedToggle = row.querySelector('.fixed-toggle-btn');
                if (fixedToggle) {
                    fixedToggle.disabled = shouldBlock;
                    if (shouldBlock) {
                        fixedToggle.style.opacity = '0.4';
                        fixedToggle.style.cursor = 'not-allowed';
                        fixedToggle.style.pointerEvents = 'none';
                    } else {
                        fixedToggle.style.opacity = '';
                        fixedToggle.style.cursor = '';
                        fixedToggle.style.pointerEvents = '';
                    }
                }

                const actionButtons = row.querySelectorAll('[data-action]');
                actionButtons.forEach(btn => {
                    btn.disabled = shouldBlock;
                    if (shouldBlock) {
                        btn.style.opacity = '0.3';
                        btn.style.cursor = 'not-allowed';
                        btn.style.pointerEvents = 'none';
                    } else {
                        btn.style.opacity = '';
                        btn.style.cursor = '';
                        btn.style.pointerEvents = '';
                    }
                });

                const mobileActions = row.querySelectorAll('.mobile-action-btn');
                mobileActions.forEach(btn => {
                    btn.disabled = shouldBlock;
                    if (shouldBlock) {
                        btn.style.opacity = '0.3';
                        btn.style.cursor = 'not-allowed';
                        btn.style.pointerEvents = 'none';
                    } else {
                        btn.style.opacity = '';
                        btn.style.cursor = '';
                        btn.style.pointerEvents = '';
                    }
                });

                const mobileFixedBtn = row.querySelector('.mobile-fixed-btn');
                if (mobileFixedBtn) {
                    mobileFixedBtn.disabled = shouldBlock;
                    if (shouldBlock) {
                        mobileFixedBtn.style.opacity = '0.3';
                        mobileFixedBtn.style.cursor = 'not-allowed';
                        mobileFixedBtn.style.pointerEvents = 'none';
                    } else {
                        mobileFixedBtn.style.opacity = '';
                        mobileFixedBtn.style.cursor = '';
                        mobileFixedBtn.style.pointerEvents = '';
                    }
                }

                if (shouldBlock) {
                    row.setAttribute('draggable', 'false');
                    row.style.cursor = 'default';
                } else {
                    row.setAttribute('draggable', 'true');
                    row.style.cursor = '';
                }
            }
        });

        const newItemTemplate = document.getElementById('new-item-template');
        if (newItemTemplate) {
            if (shouldBlock) {
                newItemTemplate.style.display = 'none';
            }
        }
    }

    const addButtons = document.querySelectorAll('[data-action="add-new-row"]');
    addButtons.forEach(btn => {
        btn.disabled = shouldBlock;
        if (shouldBlock) {
            btn.style.opacity = '0.3';
            btn.style.cursor = 'not-allowed';
            btn.style.pointerEvents = 'none';
        } else {
            btn.style.opacity = '';
            btn.style.cursor = '';
            btn.style.pointerEvents = '';
        }
    });

    console.log('[Block Fields] All fields', shouldBlock ? 'blocked' : 'unblocked');
}

// Helper function to show success messages
function showSuccessMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'fixed top-4 right-4 bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg z-50';
    messageDiv.textContent = message;
    document.body.appendChild(messageDiv);

    setTimeout(() => {
        messageDiv.remove();
    }, 3000);
}


// Money mask functions
// Money mask functions - using utils.js (applyMoneyMask, getRawValue, formatAmountForInput, formatCurrency)

function updateBudgetWarning() {
    const budgetInput = document.querySelector('input[name="budgeted_amount"]');
    if (!budgetInput) return;

    const budgetValue = parseFloat(getRawValue(budgetInput.value, window.FLOWGROUP_CONFIG.thousandSeparator, window.FLOWGROUP_CONFIG.decimalSeparator)) || 0;
    let totalEstimated = 0;
    const rows = document.querySelectorAll('tr[id^="item-"]');
    rows.forEach(row => {
        const itemId = row.id.replace('item-', '');
        if (itemId !== 'NEW' && itemId !== 'new-item-template') {
            const amountInput = row.querySelector('input[data-field="amount"]');
            if (amountInput && amountInput.value) {
                const amount = parseFloat(getRawValue(amountInput.value, window.FLOWGROUP_CONFIG.thousandSeparator, window.FLOWGROUP_CONFIG.decimalSeparator)) || 0;
                totalEstimated += amount;
            }
        }
    });

    // FIXED: Use the template container as per user request
    const warningContainer = document.getElementById('budget-warning-container');
    const warningText = document.getElementById('budget-warning-text');

    if (totalEstimated > budgetValue) {
        // Show warning and update text
        if (warningContainer) {
            warningContainer.classList.remove('hidden');
        }
        if (warningText) {
            warningText.textContent = window.FLOWGROUP_CONFIG.i18n.estimatedExpenses + ' (' + formatCurrency(totalEstimated, window.FLOWGROUP_CONFIG.currencySymbol, window.FLOWGROUP_CONFIG.thousandSeparator, window.FLOWGROUP_CONFIG.decimalSeparator) + ') ' + window.FLOWGROUP_CONFIG.i18n.exceedBudget;
        }
    } else {
        // Hide warning when total is below budget
        if (warningContainer) {
            warningContainer.classList.add('hidden');
        }
    }
}

window.deleteFlowGroup = function() {
    const flowGroupId = document.getElementById('flow-group-form').getAttribute('data-flow-group-id');
    const flowGroupName = document.querySelector('input[name="name"]').value;
    if (flowGroupId === 'NEW') {
        window.location.href = window.FLOWGROUP_CONFIG.urls.dashboard;
        return;
    }
    const confirmMsg = window.FLOWGROUP_CONFIG.i18n.deletionWarning + '<br><br><strong>"' + flowGroupName + '"</strong><br><br>' + window.FLOWGROUP_CONFIG.i18n.confirmDelete;

    // Use GenericModal.confirm instead of native confirm()
    window.GenericModal.confirm(
        confirmMsg,
        function() {
            // User confirmed - proceed with deletion
            fetch(window.FLOWGROUP_CONFIG.urls.deleteFlowGroup, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.FLOWGROUP_CSRF,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ 'flow_group_id': flowGroupId })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    window.GenericModal.alert(
                        window.FLOWGROUP_CONFIG.i18n.flowGroupDeleted,
                        window.FLOWGROUP_CONFIG.i18n.flowGroupDeletedTitle || 'Success',
                        function() {
                            window.location.href = window.FLOWGROUP_CONFIG.urls.dashboard;
                        }
                    );
                } else if (data.status === 'deleted_by_other') {
                    window.GenericModal.alert(
                        window.FLOWGROUP_CONFIG.i18n.flowGroupDeletedByUser.replace('{user}', data.deleted_by),
                        window.FLOWGROUP_CONFIG.i18n.flowGroupDeletedTitle || 'Notice',
                        function() {
                            window.location.href = window.FLOWGROUP_CONFIG.urls.dashboard;
                        }
                    );
                } else if (data.status === 'not_found') {
                    window.GenericModal.alert(
                        window.FLOWGROUP_CONFIG.i18n.anotherUser,
                        window.FLOWGROUP_CONFIG.i18n.flowGroupDeletedTitle || 'Notice',
                        function() {
                            window.location.href = window.FLOWGROUP_CONFIG.urls.dashboard;
                        }
                    );
                } else {
                    window.GenericModal.alert(window.FLOWGROUP_CONFIG.i18n.errorDeletingFlowGroup + ' ' + (data.error || ''));
                }
            })
            .catch(error => {
                console.error('Fetch Error:', error);
                window.GenericModal.alert(window.FLOWGROUP_CONFIG.i18n.networkError);
            });
        },
        window.FLOWGROUP_CONFIG.i18n.confirmDelete || 'Confirm Deletion'
    );
};

async function fetchWithRetry(url, options, maxRetries = 3) {
    let lastError;
    for (let i = 0; i < maxRetries; i++) {
        try {
            const response = await fetch(url, options);
            if (response.ok) { return response; }
            lastError = new Error(`HTTP ${response.status}`);
        } catch (error) {
            lastError = error;
        }
        if (i < maxRetries - 1) {
            await new Promise(resolve => setTimeout(resolve, Math.pow(2, i) * 1000));
        }
    }
    throw lastError;
}

window.toggleRealized = function(rowId, currentStatus) {
    const row = document.getElementById(rowId);
    if (!row) return;
    const transactionId = row.getAttribute('data-item-id');
    if (transactionId === 'NEW') return;

    // If currentStatus not provided, get it from data attribute
    if (currentStatus === undefined) {
        currentStatus = row.getAttribute('data-realized') === 'true';
    }

    const newStatus = !currentStatus;

    // Get other field values from display mode
    const description = row.querySelector('.cell-description-display')?.textContent ||
                       row.querySelector('input[data-field="description"]')?.value || '';

    // Get amount from edit input and convert from masked format
    const amountInput = row.querySelector('input[data-field="amount"]');
    const amountText = amountInput ? getRawValue(amountInput.value, window.FLOWGROUP_CONFIG.thousandSeparator, window.FLOWGROUP_CONFIG.decimalSeparator) : '0';

    // Get date from the hidden input (edit mode) which has the correct YYYY-MM-DD format
    const dateInput = row.querySelector('input[data-field="date"]');
    const dateText = dateInput ? dateInput.value : '';

    const memberSelect = row.querySelector('select[data-field="member"]');
    const memberId = memberSelect ? memberSelect.value : '';

    const isFixed = row.getAttribute('data-fixed') === 'true';

    const data = {
        'flow_group_id': document.getElementById('flow-group-form').getAttribute('data-flow-group-id'),
        'transaction_id': transactionId,
        'description': description,
        'amount': amountText,
        'date': dateText,
        'member_id': memberId,
        'realized': newStatus,
        'is_fixed': isFixed,
    };

    fetch(window.FLOWGROUP_CONFIG.urls.saveFlowItem, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.FLOWGROUP_CSRF,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Update data attributes
            row.setAttribute('data-realized', data.realized ? 'true' : 'false');
            row.setAttribute('data-amount', data.amount);

            // Update toggle visual state
            const toggleBtn = row.querySelector('.realized-toggle');
            if (toggleBtn) {
                const toggleCircle = toggleBtn.querySelector('span');

                if (data.realized) {
                    toggleBtn.classList.remove('bg-gray-300', 'dark:bg-gray-600');
                    toggleBtn.classList.add('bg-green-500');
                    if (toggleCircle) toggleCircle.classList.add('translate-x-4');
                    row.classList.remove('row-not-realized');
                    row.classList.add('row-realized');
                } else {
                    toggleBtn.classList.remove('bg-green-500');
                    toggleBtn.classList.add('bg-gray-300', 'dark:bg-gray-600');
                    if (toggleCircle) toggleCircle.classList.remove('translate-x-4');
                    row.classList.remove('row-realized');
                    row.classList.add('row-not-realized');
                }

                toggleBtn.setAttribute('data-toggle', 'realized');
                toggleBtn.setAttribute('data-item-id', rowId);
                toggleBtn.setAttribute('data-current-state', data.realized ? 'true' : 'false');
            }

            // Reset mobile swipe position
            row.style.transform = 'translateX(0)';
            row.classList.remove('actions-revealed', 'fixed-revealed');

            // Update summary
            updateSummary();
        } else {
            alert(window.FLOWGROUP_CONFIG.i18n.errorUpdatingStatus + ': ' + data.error);
        }
    })
    .catch(error => {
        console.error('Fetch Error:', error);
        alert(window.FLOWGROUP_CONFIG.i18n.networkError);
    });
};

window.toggleTransactionFixed = function(rowId) {
    const row = document.getElementById(rowId);
    if (!row) {
        console.error('[toggleTransactionFixed] Row not found:', rowId);
        return;
    }
    const itemId = rowId.replace('item-', '');
    if (itemId === 'NEW' || itemId === 'new-item-template') {
        alert(window.FLOWGROUP_CONFIG.i18n.pleaseSaveTransactionBeforeFixed);
        return;
    }

    const currentFixed = row.getAttribute('data-fixed') === 'true';
    const newFixed = !currentFixed;

    const requestData = { 'transaction_id': itemId, 'fixed': newFixed };
    console.log('[toggleTransactionFixed] Sending request:', requestData);

    fetch(window.FLOWGROUP_CONFIG.urls.toggleTransactionFixed, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.FLOWGROUP_CSRF, 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify(requestData)
    })
    .then(response => {
        if (!response.ok) {
            console.error('[toggleTransactionFixed] HTTP error:', response.status, response.statusText);
            return response.json().then(err => Promise.reject(err));
        }
        return response.json();
    })
    .then(data => {
        console.log('[toggleTransactionFixed] Response:', data);
        if (data.status === 'success') {
            row.setAttribute('data-fixed', newFixed.toString());

            // Update row class for fixed border (mobile)
            if (newFixed) {
                row.classList.add('row-fixed');
            } else {
                row.classList.remove('row-fixed');
            }

            // Update desktop fixed button
            const fixedBtn = row.querySelector('.fixed-toggle-btn');
            if (fixedBtn) {
                if (newFixed) {
                    fixedBtn.classList.remove('text-gray-400', 'dark:text-gray-500');
                    fixedBtn.classList.add('text-blue-600', 'dark:text-blue-400');
                } else {
                    fixedBtn.classList.remove('text-blue-600', 'dark:text-blue-400');
                    fixedBtn.classList.add('text-gray-400', 'dark:text-gray-500');
                }
                fixedBtn.setAttribute('data-action', 'toggle-transaction-fixed');
                fixedBtn.setAttribute('data-row-id', rowId);
            }

            // Update mobile fixed button
            const mobileFixedBtn = row.querySelector('.mobile-fixed-btn');
            if (mobileFixedBtn) {
                if (newFixed) {
                    mobileFixedBtn.classList.add('active');
                } else {
                    mobileFixedBtn.classList.remove('active');
                }
                mobileFixedBtn.setAttribute('data-action', 'toggle-transaction-fixed');
                mobileFixedBtn.setAttribute('data-row-id', rowId);
            }

            // CRITICAL FIX: Return row to original position after toggling fixed (mobile)
            row.style.transform = 'translateX(0)';
            row.classList.remove('actions-revealed', 'fixed-revealed');
            row.setAttribute('draggable', 'true');

            showSuccessMessage(newFixed ? window.FLOWGROUP_CONFIG.i18n.transactionMarkedFixed : window.FLOWGROUP_CONFIG.i18n.transactionNotFixed);
        } else {
            console.error('[toggleTransactionFixed] Error:', data.error || data.message);
            alert(data.error || data.message || window.FLOWGROUP_CONFIG.i18n.networkError);
        }
    })
    .catch(error => {
        console.error('[toggleTransactionFixed] Catch error:', error);
        const errorMessage = error.error || error.message || error.toString();
        alert(window.FLOWGROUP_CONFIG.i18n.networkError + ': ' + errorMessage);
    });
};

window.toggleNewItemFixed = function(rowId) {
    const row = document.getElementById(rowId);
    if (!row) return;
    const currentFixed = row.getAttribute('data-fixed') === 'true';
    const newFixed = !currentFixed;
    row.setAttribute('data-fixed', newFixed.toString());
    const fixedBtn = row.querySelector('.fixed-toggle-btn');
    const mobileFixedBtn = row.querySelector('.mobile-fixed-btn');
    if (newFixed) {
        if (fixedBtn) {
            fixedBtn.classList.remove('text-gray-400', 'dark:text-gray-500');
            fixedBtn.classList.add('text-blue-600', 'dark:text-blue-400');
        }
        if (mobileFixedBtn) {
            mobileFixedBtn.classList.add('active');
        }
    } else {
        if (fixedBtn) {
            fixedBtn.classList.remove('text-blue-600', 'dark:text-blue-400');
            fixedBtn.classList.add('text-gray-400', 'dark:text-gray-500');
        }
        if (mobileFixedBtn) {
            mobileFixedBtn.classList.remove('active');
        }
    }
};

window.addNewRow = function() {
    console.log('[addNewRow] Called');
    const templateRow = document.getElementById('new-item-template');
    if (!templateRow) {
        console.error('[addNewRow] Template not found');
        return;
    }

    // Debug current state
    const hasHiddenClass = templateRow.classList.contains('hidden');
    const computedDisplay = window.getComputedStyle(templateRow).display;
    console.log('[addNewRow] Has hidden class:', hasHiddenClass, 'Computed display:', computedDisplay);

    // Check if template is already visible by checking both class and display
    const isHidden = hasHiddenClass || computedDisplay === 'none';

    if (isHidden) {
        console.log('[addNewRow] Template is hidden, showing it now');

        // CRITICAL FIX: Hide empty state row if it exists (FlowGroup with no items)
        const emptyStateRow = document.getElementById('empty-state-row');
        if (emptyStateRow) {
            emptyStateRow.style.display = 'none';
            console.log('[addNewRow] Empty state row hidden');
        }

        // Ensure date field is initialized BEFORE showing the row
        const dateInput = templateRow.querySelector('input[data-field="date"]');
        if (dateInput) {
            const today = new Date().toISOString().split('T')[0];
            dateInput.value = today;
            const [year, month, day] = today.split('-');
            const displayValue = `${day}/${month}`;
            dateInput.setAttribute('data-display-value', displayValue);
        }

        // CRITICAL FIX: Remove both class and inline style
        templateRow.classList.remove('hidden');
        templateRow.style.display = '';  // Remove any inline display: none

        console.log('[addNewRow] Template visible, scrolling into view');

        // Scroll template into view
        templateRow.scrollIntoView({ behavior: 'smooth', block: 'center' });

        const descInput = templateRow.querySelector('input[data-field="description"]');
        if (descInput) {
            setTimeout(() => {
                descInput.focus();
                console.log('[addNewRow] Focused on description input');
            }, 100);
        }
    } else {
        // Template already visible, just focus
        console.log('[addNewRow] Template already visible, just focusing');
        const descInput = templateRow.querySelector('input[data-field="description"]');
        if (descInput) {
            descInput.focus();
        }
    }
};

window.saveItem = function(rowId) {
    console.log('[saveItem] Called with rowId:', rowId);
    const row = document.getElementById(rowId);
    if (!row) {
        console.error('[saveItem] Row not found:', rowId);
        return;
    }

    // CRITICAL FIX: Prevent double save - check if already saving
    if (row.dataset.saving === 'true') {
        console.log('[saveItem] Already saving, ignoring duplicate call');
        return;
    }
    row.dataset.saving = 'true';

    // FIXED: Use Dashboard pattern - always get transaction_id from data-item-id attribute
    const transactionId = row.getAttribute('data-item-id');
    const isNew = (rowId === 'new-item-template' || !transactionId || transactionId === 'NEW');

    const descInput = row.querySelector('input[data-field="description"]');
    const amountInput = row.querySelector('input[data-field="amount"]');
    const dateInput = row.querySelector('input[data-field="date"]');
    const memberSelect = row.querySelector('select[data-field="member"]');
    if (!descInput || !amountInput || !dateInput) {
        alert(window.FLOWGROUP_CONFIG.i18n.descriptionAmountDateRequired);
        return;
    }
    const description = descInput.value.trim();
    const amount = getRawValue(amountInput.value, window.FLOWGROUP_CONFIG.thousandSeparator, window.FLOWGROUP_CONFIG.decimalSeparator);
    const date = dateInput.value;
    const memberId = memberSelect ? memberSelect.value : '';

    // Get realized value - for new items read from toggle, for existing read from attribute
    let realized = false;
    if (isNew) {
        const toggleNew = row.querySelector('.realized-toggle-new');
        realized = toggleNew ? toggleNew.classList.contains('bg-green-500') : false;
    } else {
        realized = row.getAttribute('data-realized') === 'true';
    }

    // Get fixed value - for new items read from toggle, for existing read from attribute
    let fixed = false;
    if (isNew) {
        const toggleFixedNew = row.querySelector('.fixed-toggle-new');
        fixed = toggleFixedNew ? toggleFixedNew.getAttribute('data-fixed') === 'true' : false;
    } else {
        fixed = row.getAttribute('data-fixed') === 'true';
    }

    if (!description || !amount || !date) {
        alert(window.FLOWGROUP_CONFIG.i18n.descriptionAmountDateRequired);
        return;
    }

    console.log('[saveItem] Transaction ID:', transactionId);
    console.log('[saveItem] Is New:', isNew);
    console.log('[saveItem] Description:', description);
    console.log('[saveItem] Amount:', amount);

    const flowGroupId = document.getElementById('flow-group-form').getAttribute('data-flow-group-id');

    // FIXED: Use Dashboard pattern - send 'transaction_id' (backend expects this field name!)
    // For new items, send null, not 'NEW'
    const data = {
        flow_group_id: flowGroupId,
        transaction_id: isNew ? null : transactionId,  // Send null for new items
        description: description,
        amount: amount,
        date: date,
        member_id: memberId,
        is_fixed: fixed,  // Backend expects 'is_fixed'
        realized: realized
    };

    console.log('[saveItem] Sending data:', JSON.stringify(data, null, 2));

    fetch(window.FLOWGROUP_CONFIG.urls.saveFlowItem, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.FLOWGROUP_CSRF, 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify(data)
    })
    .then(response => {
        if (!response.ok) {
            console.error('[saveItem] HTTP error:', response.status, response.statusText);
            return response.json().then(err => Promise.reject(err)).catch(() => Promise.reject({ error: `HTTP ${response.status}` }));
        }
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            if (isNew) {
                // Clone the template row instead of converting it
                const templateRow = row;
                const newRow = templateRow.cloneNode(true);

                // Insert the new row before the template
                templateRow.parentNode.insertBefore(newRow, templateRow);

                // Update row ID and attributes
                newRow.id = 'item-' + data.transaction_id;
                newRow.setAttribute('data-item-id', data.transaction_id);
                newRow.setAttribute('data-mode', 'display');
                newRow.setAttribute('data-realized', data.realized ? 'true' : 'false');
                newRow.setAttribute('data-fixed', data.is_fixed ? 'true' : 'false');
                newRow.setAttribute('draggable', 'true');
                // Remove mobile-initialized flag so new row gets touch listeners
                newRow.removeAttribute('data-mobile-initialized');

                // Add row status classes for mobile color indication
                newRow.classList.add('draggable-row');
                if (data.realized) {
                    newRow.classList.add('row-realized');
                    newRow.classList.remove('row-not-realized');
                } else {
                    newRow.classList.add('row-not-realized');
                    newRow.classList.remove('row-realized');
                }
                if (data.is_fixed) {
                    newRow.classList.add('row-fixed');
                }

                // Update the drag handle cell
                const dragCell = newRow.querySelector('.drag-handle-cell');
                if (dragCell) {
                    // Build mobile fixed button HTML
                    let mobileFixedBtnHtml = '';
                    if (window.FLOWGROUP_CONFIG.memberRole !== 'CHILD') {
                        const activeClass = data.is_fixed ? 'active' : '';
                        mobileFixedBtnHtml = `<div class="mobile-fixed-btn-container">
                            <button type="button" data-action="toggle-transaction-fixed" data-row-id="item-${data.transaction_id}"
                                class="mobile-fixed-btn ${activeClass}" title="Mark as recurring expense">
                                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5"
                                        d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8m0-5v5h5" />
                                </svg>
                            </button>
                        </div>`;
                    }

                    dragCell.innerHTML = mobileFixedBtnHtml +
                        '<span class="material-symbols-outlined text-gray-400 dark:text-gray-500 drag-handle cursor-grab active:cursor-grabbing">drag_indicator</span>' +
                        '<button type="button" data-action="save" data-row-id="item-' + data.transaction_id + '" class="edit-save-icon" style="display: none;">' +
                        '<span class="material-symbols-outlined text-green-500 text-2xl">check_circle</span></button>';
                }

                // Update action buttons
                const actionsDisplay = newRow.querySelector('.actions-display');
                if (actionsDisplay) {
                    actionsDisplay.innerHTML =
                        '<button type="button" data-action="edit" data-row-id="item-' + data.transaction_id + '" class="p-1 text-slate-500 hover:text-primary">' +
                        '<span class="material-symbols-outlined text-lg">edit</span></button>' +
                        '<button type="button" data-action="delete" data-row-id="item-' + data.transaction_id + '" class="p-1 text-slate-500 hover:text-red-500">' +
                        '<span class="material-symbols-outlined text-lg">delete</span></button>';
                    actionsDisplay.classList.remove('hidden');
                }

                // Hide action edit buttons
                const actionsEdit = newRow.querySelector('.actions-edit');
                if (actionsEdit) {
                    actionsEdit.classList.add('hidden');
                }

                // Convert Realized toggle
                const realizedToggleNew = newRow.querySelector('.realized-toggle-new');
                if (realizedToggleNew) {
                    const realizedCell = realizedToggleNew.closest('td');
                    const bgClass = data.realized ? 'bg-green-500' : 'bg-gray-300 dark:bg-gray-600';
                    const translateClass = data.realized ? 'translate-x-4' : '';
                    realizedCell.innerHTML =
                        '<div class="flex items-center justify-center">' +
                        '<button type="button" data-toggle="realized" data-item-id="item-' + data.transaction_id + '" data-current-state="' + (data.realized ? 'true' : 'false') + '" ' +
                        'class="realized-toggle relative inline-block w-10 h-6 transition duration-200 ease-in-out rounded-full cursor-pointer ' + bgClass + '">' +
                        '<span class="absolute left-1 top-1 inline-block w-4 h-4 transition-transform duration-200 ease-in-out transform bg-white rounded-full ' + translateClass + '"></span>' +
                        '</button></div>';
                }

                // Convert Fixed toggle
                const fixedToggleNew = newRow.querySelector('.fixed-toggle-new');
                if (fixedToggleNew && window.FLOWGROUP_CONFIG.memberRole !== 'CHILD') {
                    const fixedCell = fixedToggleNew.closest('td');
                    const bgClass = data.is_fixed ? 'bg-blue-600 text-white hover:bg-blue-700' : 'bg-gray-200 dark:bg-gray-700 text-gray-400 dark:text-gray-500 hover:bg-blue-200 dark:hover:bg-blue-900/30';
                    fixedCell.innerHTML =
                        '<div class="flex items-center justify-center">' +
                        '<button type="button" data-action="toggle-transaction-fixed" data-row-id="item-' + data.transaction_id + '" ' +
                        'class="fixed-toggle-btn inline-flex items-center justify-center w-8 h-8 rounded transition-all duration-200 ' + bgClass + '" ' +
                        'title="Mark as recurring expense">' +
                        '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8m0-5v5h5" />' +
                        '</svg></button></div>';
                }

                // Create date display
                const dateDisplayCell = newRow.querySelector('.cell-date-display');
                if (dateDisplayCell) {
                    const dateObj = new Date(data.date + 'T00:00:00');
                    const day = String(dateObj.getDate()).padStart(2, '0');
                    const month = String(dateObj.getMonth() + 1).padStart(2, '0');
                    dateDisplayCell.innerHTML =
                        '<span class="date-full">' + data.date + '</span>' +
                        '<span class="date-short">' + day + '/' + month + '</span>';
                }

                // Add mobile action buttons to amount cell
                const budgetDisplayCell = newRow.querySelector('.cell-budget-display');
                if (budgetDisplayCell) {
                    budgetDisplayCell.classList.add('amount-cell-with-actions');
                    let mobileActionsDiv = budgetDisplayCell.querySelector('.mobile-actions-btns');
                    if (!mobileActionsDiv) {
                        mobileActionsDiv = document.createElement('div');
                        mobileActionsDiv.className = 'mobile-actions-btns';
                        budgetDisplayCell.appendChild(mobileActionsDiv);
                    }
                    mobileActionsDiv.innerHTML =
                        '<button type="button" data-action="edit" data-row-id="item-' + data.transaction_id + '" class="mobile-action-btn edit-btn">' +
                        '<span class="material-symbols-outlined">edit</span></button>' +
                        '<button type="button" data-action="delete" data-row-id="item-' + data.transaction_id + '" class="mobile-action-btn delete-btn">' +
                        '<span class="material-symbols-outlined">delete</span></button>';
                }

                // Switch to display mode and populate values
                toggleEditMode('item-' + data.transaction_id, false);
                updateRowDisplay('item-' + data.transaction_id, { id: data.transaction_id, description: data.description, amount: data.amount, date: data.date, member_id: data.member_id, realized: data.realized, fixed: data.is_fixed });

                // Reset and hide the template row
                const descInput = templateRow.querySelector('input[data-field="description"]');
                if (descInput) descInput.value = '';

                const amountInput = templateRow.querySelector('input[data-field="amount"]');
                if (amountInput) amountInput.value = '0' + window.FLOWGROUP_CONFIG.decimalSeparator + '00';

                const dateInput = templateRow.querySelector('input[data-field="date"]');
                if (dateInput) {
                    const today = new Date().toISOString().split('T')[0];
                    dateInput.value = today;
                    const [year, month, day] = today.split('-');
                    dateInput.setAttribute('data-display-value', `${day}/${month}`);
                }

                // Reset realized toggle
                const realizedToggle = templateRow.querySelector('.realized-toggle-new');
                if (realizedToggle) {
                    const toggleCircle = realizedToggle.querySelector('span');
                    realizedToggle.classList.remove('bg-green-500');
                    realizedToggle.classList.add('bg-gray-300', 'dark:bg-gray-600');
                    if (toggleCircle) toggleCircle.classList.remove('translate-x-4');
                }

                // Reset fixed toggle
                const fixedToggle = templateRow.querySelector('.fixed-toggle-new');
                if (fixedToggle) {
                    fixedToggle.setAttribute('data-fixed', 'false');
                    fixedToggle.classList.remove('bg-blue-600', 'text-white', 'hover:bg-blue-700');
                    fixedToggle.classList.add('bg-gray-200', 'dark:bg-gray-700', 'text-gray-400', 'dark:text-gray-500', 'hover:bg-blue-200', 'dark:hover:bg-blue-900/30');
                }

                // Hide template
                templateRow.classList.add('hidden');
                templateRow.style.display = 'none';

                // CRITICAL FIX: Hide empty state row permanently after first item is saved
                const emptyStateRow = document.getElementById('empty-state-row');
                if (emptyStateRow) {
                    emptyStateRow.style.display = 'none';
                    console.log('[saveItem] Empty state row hidden permanently (first item saved)');
                }

                // Update summary and warning
                updateSummary();
                updateBudgetWarning();

                // Re-initialize features
                initializeDragAndDrop();
                initMobileExpenseFeatures();

                // Reset saving flag
                row.dataset.saving = 'false';
            } else {
                // Existing item - just update display
                const itemData = { id: data.transaction_id, description: data.description, amount: data.amount, date: data.date, member_id: data.member_id, realized: data.realized, fixed: data.is_fixed };
                updateRowDisplay(rowId, itemData);
                updateSummary();
                updateBudgetWarning();

                // Reset saving flag
                row.dataset.saving = 'false';
            }
        } else if (data.status === 'error' && data.error === 'duplicate_name') {
            alert(window.FLOWGROUP_CONFIG.i18n.duplicateName);
            row.dataset.saving = 'false';
        } else {
            alert(data.error || window.FLOWGROUP_CONFIG.i18n.networkError);
            row.dataset.saving = 'false';
        }
    })
    .catch(error => {
        console.error('[saveItem] Error:', error);
        const errorMessage = error.error || error.message || error.toString();
        alert(window.FLOWGROUP_CONFIG.i18n.networkError + ': ' + errorMessage);
        row.dataset.saving = 'false';
    });
};

function updateRowDisplay(rowId, data) {
    const row = document.getElementById(rowId);
    if (!row) return;
    row.setAttribute('data-realized', data.realized ? 'true' : 'false');
    row.setAttribute('data-fixed', data.fixed ? 'true' : 'false');
    const descInput = row.querySelector('input[data-field="description"]');
    const amountInput = row.querySelector('input[data-field="amount"]');
    const dateInput = row.querySelector('input[data-field="date"]');
    const memberSelect = row.querySelector('select[data-field="member"]');
    if (descInput) descInput.value = data.description;
    if (amountInput) amountInput.value = formatAmountForInput(data.amount, window.FLOWGROUP_CONFIG.thousandSeparator, window.FLOWGROUP_CONFIG.decimalSeparator);
    if (dateInput) dateInput.value = data.date;
    if (memberSelect) memberSelect.value = data.member_id || '';

    // Update date display (date-full and date-short spans)
    const dateDisplayCell = row.querySelector('.cell-date-display');
    if (dateDisplayCell && data.date) {
        const dateObj = new Date(data.date + 'T00:00:00');
        const day = String(dateObj.getDate()).padStart(2, '0');
        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
        dateDisplayCell.innerHTML = `
            <span class="date-full">${data.date}</span>
            <span class="date-short">${day}/${month}</span>
        `;
    }

    // Ensure mobile action buttons exist in amount cell
    const budgetDisplayCell = row.querySelector('.cell-budget-display');
    if (budgetDisplayCell) {
        budgetDisplayCell.classList.add('amount-cell-with-actions');
        let mobileActionsDiv = budgetDisplayCell.querySelector('.mobile-actions-btns');
        if (!mobileActionsDiv) {
            // Create mobile actions if they don't exist
            mobileActionsDiv = document.createElement('div');
            mobileActionsDiv.className = 'mobile-actions-btns';
            mobileActionsDiv.innerHTML =
                '<button type="button" data-action="edit" data-row-id="' + rowId + '" class="mobile-action-btn edit-btn">' +
                '<span class="material-symbols-outlined">edit</span></button>' +
                '<button type="button" data-action="delete" data-row-id="' + rowId + '" class="mobile-action-btn delete-btn">' +
                '<span class="material-symbols-outlined">delete</span></button>';
            budgetDisplayCell.appendChild(mobileActionsDiv);
        }
    }

    const toggle = row.querySelector('.realized-toggle');
    const toggleCircle = toggle ? toggle.querySelector('span') : null;
    if (toggle) {
        if (data.realized) {
            toggle.classList.remove('bg-gray-300', 'dark:bg-gray-600');
            toggle.classList.add('bg-green-500');
            if (toggleCircle) toggleCircle.classList.add('translate-x-4');
            row.classList.remove('row-not-realized');
            row.classList.add('row-realized');
        } else {
            toggle.classList.remove('bg-green-500');
            toggle.classList.add('bg-gray-300', 'dark:bg-gray-600');
            if (toggleCircle) toggleCircle.classList.remove('translate-x-4');
            row.classList.remove('row-realized');
            row.classList.add('row-not-realized');
        }
        toggle.setAttribute('data-toggle', 'realized');
        toggle.setAttribute('data-item-id', rowId);
        toggle.setAttribute('data-current-state', data.realized ? 'true' : 'false');
    }
    const fixedBtn = row.querySelector('.fixed-toggle-btn');
    const mobileFixedBtn = row.querySelector('.mobile-fixed-btn');
    if (data.fixed) {
        if (fixedBtn) {
            fixedBtn.classList.remove('text-gray-400', 'dark:text-gray-500');
            fixedBtn.classList.add('text-blue-600', 'dark:text-blue-400');
        }
        if (mobileFixedBtn) {
            mobileFixedBtn.classList.remove('text-gray-400', 'dark:text-gray-500');
            mobileFixedBtn.classList.add('text-blue-600', 'dark:text-blue-400');
        }
    } else {
        if (fixedBtn) {
            fixedBtn.classList.remove('text-blue-600', 'dark:text-blue-400');
            fixedBtn.classList.add('text-gray-400', 'dark:text-gray-500');
        }
        if (mobileFixedBtn) {
            mobileFixedBtn.classList.remove('text-blue-600', 'dark:text-blue-400');
            mobileFixedBtn.classList.add('text-gray-400', 'dark:text-gray-500');
        }
    }
    toggleEditMode(rowId, false);
}

window.toggleEditMode = function(rowId, startEdit) {
    const row = document.getElementById(rowId);
    if (!row) {
        console.error('[toggleEditMode] Row not found:', rowId);
        return;
    }

    const itemId = rowId.replace('item-', '');
    if (itemId === 'NEW' || itemId === 'new-item-template') return;

    // Find the action divs
    const actionsDisplay = row.querySelector('.actions-display');
    const actionsEdit = row.querySelector('.actions-edit');

    // Find all display/edit cell pairs
    const displayCells = row.querySelectorAll('[class*="-display"]');
    const editCells = row.querySelectorAll('[class*="-edit"]');

    if (startEdit) {
        // Enter edit mode
        row.classList.add('editing');
        row.setAttribute('data-mode', 'edit');

        // CRITICAL FIX: Disable drag when in edit mode (allows save button to work!)
        row.setAttribute('draggable', 'false');
        row.classList.remove('draggable-row');

        // MOBILE FIX: Reset row position when entering edit mode
        row.style.transform = 'translateX(0)';
        row.classList.remove('actions-revealed', 'fixed-revealed');

        // MOBILE FIX: Show save button, hide drag handle
        const dragHandle = row.querySelector('.drag-handle');
        const saveIcon = row.querySelector('.edit-save-icon');
        if (dragHandle) dragHandle.style.display = 'none';
        if (saveIcon) saveIcon.style.display = 'inline-block';

        // Hide display cells, show edit cells
        displayCells.forEach(cell => {
            if (cell.classList.contains('actions-display')) return; // Skip action buttons
            cell.classList.add('hidden');
        });
        editCells.forEach(cell => {
            if (cell.classList.contains('actions-edit')) return; // Skip action buttons
            cell.classList.remove('hidden');
        });

        // Show edit actions, hide display actions
        if (actionsDisplay) actionsDisplay.classList.add('hidden');
        if (actionsEdit) actionsEdit.classList.remove('hidden');

        console.log('[toggleEditMode] Entered edit mode for:', rowId);
    } else {
        // Exit edit mode
        row.classList.remove('editing');
        row.setAttribute('data-mode', 'display');

        // CRITICAL FIX: Re-enable drag when exiting edit mode
        row.setAttribute('draggable', 'true');
        row.classList.add('draggable-row');

        // MOBILE FIX: Reset row position when exiting edit mode
        row.style.transform = 'translateX(0)';
        row.classList.remove('actions-revealed', 'fixed-revealed');

        // MOBILE FIX: Show drag handle, hide save button
        const dragHandle = row.querySelector('.drag-handle');
        const saveIcon = row.querySelector('.edit-save-icon');
        if (dragHandle) dragHandle.style.display = 'inline';
        if (saveIcon) saveIcon.style.display = 'none';

        // Show display cells, hide edit cells
        displayCells.forEach(cell => {
            if (cell.classList.contains('actions-display')) return; // Skip action buttons
            cell.classList.remove('hidden');
        });
        editCells.forEach(cell => {
            if (cell.classList.contains('actions-edit')) return; // Skip action buttons
            cell.classList.add('hidden');
        });

        // Show display actions, hide edit actions
        if (actionsDisplay) actionsDisplay.classList.remove('hidden');
        if (actionsEdit) actionsEdit.classList.add('hidden');

        console.log('[toggleEditMode] Exited edit mode for:', rowId);
    }
};

window.cancelNewRow = function(rowId) {
    console.log('[cancelNewRow] Called with rowId:', rowId);
    const template = document.getElementById('new-item-template');
    if (!template) {
        console.error('[cancelNewRow] Template not found');
        return;
    }

    console.log('[cancelNewRow] Before hide - classList:', template.classList.toString(), 'display:', template.style.display, 'computedDisplay:', window.getComputedStyle(template).display);

    // Hide the template
    template.classList.add('hidden');
    // CRITICAL FIX: Also set inline style to ensure it's fully hidden
    template.style.display = 'none';
    // CRITICAL FIX: Reset transform from swipe gesture
    template.style.transform = 'translateX(0)';
    // CRITICAL FIX: Reset mobile swipe state
    template.classList.remove('actions-revealed', 'fixed-revealed');

    console.log('[cancelNewRow] After hide - classList:', template.classList.toString(), 'display:', template.style.display, 'computedDisplay:', window.getComputedStyle(template).display);

    // CRITICAL FIX: Show empty state row if there are no items (FlowGroup is empty)
    const tbody = document.getElementById('expense-items-body');
    if (tbody) {
        const itemRows = tbody.querySelectorAll('tr[id^="item-"]:not(#new-item-template)');
        if (itemRows.length === 0) {
            // No items exist, show empty state
            const emptyStateRow = document.getElementById('empty-state-row');
            if (emptyStateRow) {
                emptyStateRow.style.display = '';
                console.log('[cancelNewRow] Empty state row shown (no items)');
            }
        }
    }

    // Reset all inputs
    const inputs = template.querySelectorAll('input, select');
    inputs.forEach(input => {
        if (input.type === 'text' || input.type === 'date') {
            if (input.getAttribute('data-field') === 'amount') {
                input.value = '0' + window.FLOWGROUP_CONFIG.decimalSeparator + '00';
            } else if (input.getAttribute('data-field') !== 'date') {
                input.value = '';
            }
        } else if (input.tagName === 'SELECT') {
            input.selectedIndex = 0;
        }
    });

    // Reset realized toggle
    const realizedToggle = template.querySelector('.realized-toggle-new');
    if (realizedToggle) {
        const toggleCircle = realizedToggle.querySelector('span');
        realizedToggle.classList.remove('bg-green-500');
        realizedToggle.classList.add('bg-gray-300', 'dark:bg-gray-600');
        if (toggleCircle) toggleCircle.classList.remove('translate-x-4');
    }

    // Reset fixed toggle
    const fixedToggle = template.querySelector('.fixed-toggle-new');
    if (fixedToggle) {
        fixedToggle.setAttribute('data-fixed', 'false');
        fixedToggle.classList.remove('bg-blue-600', 'text-white', 'hover:bg-blue-700');
        fixedToggle.classList.add('bg-gray-200', 'dark:bg-gray-700', 'text-gray-400', 'dark:text-gray-500', 'hover:bg-blue-200', 'dark:hover:bg-blue-900/30');
    }

    console.log('[cancelNewRow] Template hidden and reset');
};

window.deleteItem = async function(rowId) {
    const row = document.getElementById(rowId);
    if (!row) return;
    const itemId = rowId.replace('item-', '');
    if (itemId === 'NEW') return;

    // Use GenericModal.confirm (returns Promise)
    const confirmed = await window.GenericModal.confirm(
        window.FLOWGROUP_CONFIG.i18n.confirmDeleteItem,
        window.FLOWGROUP_CONFIG.i18n.confirmDeleteTitle || 'Confirm Deletion'
    );

    if (!confirmed) {
        return; // User cancelled
    }

    // User confirmed - proceed with deletion
    fetch(window.FLOWGROUP_CONFIG.urls.deleteFlowItem, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.FLOWGROUP_CSRF, 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({ transaction_id: itemId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            row.remove();
            updateSummary();
            updateBudgetWarning();
        } else {
            window.GenericModal.alert(data.error || window.FLOWGROUP_CONFIG.i18n.networkError);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        window.GenericModal.alert(window.FLOWGROUP_CONFIG.i18n.networkError);
    });
};

function initializeDragAndDrop() {
    const tbody = document.getElementById('expense-items-body');
    if (!tbody) return;
    let draggedElement = null;
    let touchStartY = 0;
    let touchCurrentY = 0;
    let placeholder = null;
    tbody.addEventListener('touchstart', handleTouchDragStart, { passive: false });
    tbody.addEventListener('touchmove', handleTouchDragMove, { passive: false });
    tbody.addEventListener('touchend', handleTouchDragEnd, { passive: false });
    tbody.addEventListener('dragstart', handleDragStart);
    tbody.addEventListener('dragover', handleDragOver);
    tbody.addEventListener('dragenter', handleDragEnter);
    tbody.addEventListener('dragleave', handleDragLeave);
    tbody.addEventListener('drop', handleDrop);
    tbody.addEventListener('dragend', handleDragEnd);
    function handleTouchDragStart(e) {
        // MOBILE FIX: Only activate drag if touch started on drag handle
        const dragHandle = e.target.closest('.drag-handle, .drag-handle-cell');
        if (!dragHandle) return; // Not touching drag handle, allow swipe gestures

        const target = e.target.closest('tr[draggable="true"]');
        if (!target) return;
        const itemId = target.id.replace('item-', '');
        if (itemId === 'NEW' || itemId === 'new-item-template') return;
        draggedElement = target;
        touchStartY = e.touches[0].clientY;
        placeholder = document.createElement('tr');
        placeholder.className = 'placeholder-row';
        placeholder.innerHTML = '<td colspan="100%" class="h-16 bg-blue-100 dark:bg-blue-900/30 border-2 border-dashed border-blue-400"></td>';
        draggedElement.style.opacity = '0.5';
        e.preventDefault();
    }
    function handleTouchDragMove(e) {
        if (!draggedElement) return;
        touchCurrentY = e.touches[0].clientY;
        const deltaY = touchCurrentY - touchStartY;
        draggedElement.style.transform = `translateY(${deltaY}px)`;
        const rows = Array.from(tbody.querySelectorAll('tr[id^="item-"]')).filter(row => {
            const id = row.id.replace('item-', '');
            return id !== 'NEW' && id !== 'new-item-template' && row !== draggedElement;
        });
        let insertBefore = null;
        rows.forEach(row => {
            const box = row.getBoundingClientRect();
            const offset = touchCurrentY - box.top - box.height / 2;
            if (offset < 0 && !insertBefore) { insertBefore = row; }
        });
        if (placeholder.parentNode) { placeholder.remove(); }
        if (insertBefore) {
            tbody.insertBefore(placeholder, insertBefore);
        } else {
            tbody.appendChild(placeholder);
        }
        e.preventDefault();
    }
    function handleTouchDragEnd(e) {
        if (!draggedElement) return;
        draggedElement.style.opacity = '';
        draggedElement.style.transform = '';
        if (placeholder.parentNode) {
            tbody.insertBefore(draggedElement, placeholder);
            placeholder.remove();
            reorderItems();
        }
        draggedElement = null;
        touchStartY = 0;
        touchCurrentY = 0;
        e.preventDefault();
    }
    function handleDragStart(e) {
        const target = e.target.closest('tr[draggable="true"]');
        if (!target) return;
        const itemId = target.id.replace('item-', '');
        if (itemId === 'NEW' || itemId === 'new-item-template') {
            e.preventDefault();
            return;
        }
        draggedElement = target;
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/html', target.innerHTML);
        setTimeout(() => { target.style.opacity = '0.5'; }, 0);
    }
    function handleDragOver(e) {
        if (e.preventDefault) { e.preventDefault(); }
        e.dataTransfer.dropEffect = 'move';
        return false;
    }
    function handleDragEnter(e) {
        const target = e.target.closest('tr[id^="item-"]');
        if (!target || target === draggedElement) return;
        const itemId = target.id.replace('item-', '');
        if (itemId === 'NEW' || itemId === 'new-item-template') return;
        target.classList.add('drag-over');
    }
    function handleDragLeave(e) {
        const target = e.target.closest('tr[id^="item-"]');
        if (!target) return;
        target.classList.remove('drag-over');
    }
    function handleDrop(e) {
        if (e.stopPropagation) { e.stopPropagation(); }
        const target = e.target.closest('tr[id^="item-"]');
        if (!target || target === draggedElement) return;
        const itemId = target.id.replace('item-', '');
        if (itemId === 'NEW' || itemId === 'new-item-template') return;
        if (draggedElement !== target) {
            const allRows = Array.from(tbody.querySelectorAll('tr[id^="item-"]'));
            const draggedIndex = allRows.indexOf(draggedElement);
            const targetIndex = allRows.indexOf(target);
            if (draggedIndex < targetIndex) {
                tbody.insertBefore(draggedElement, target.nextSibling);
            } else {
                tbody.insertBefore(draggedElement, target);
            }
            reorderItems();
        }
        return false;
    }
    function handleDragEnd(e) {
        const target = e.target.closest('tr');
        if (target) { target.style.opacity = ''; }
        const allRows = tbody.querySelectorAll('tr[id^="item-"]');
        allRows.forEach(row => { row.classList.remove('drag-over'); });
        draggedElement = null;
    }
}

function reorderItems() {
    const tbody = document.getElementById('expense-items-body');
    if (!tbody) return;
    const rows = Array.from(tbody.querySelectorAll('tr[id^="item-"]')).filter(row => {
        const id = row.id.replace('item-', '');
        return id !== 'NEW' && id !== 'new-item-template';
    });
    const order = rows.map((row, index) => ({
        id: row.id.replace('item-', ''),
        position: index
    }));
    fetch(window.FLOWGROUP_CONFIG.urls.reorderFlowItems, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.FLOWGROUP_CSRF, 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({ order: order })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status !== 'success') {
            console.error('Error reordering items:', data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert(window.FLOWGROUP_CONFIG.i18n.networkErrorSavingOrder);
    });
}

function initializeNewItemToggle() {
    // REMOVED: Template already has 'hidden' class in HTML
    // Adding display: none inline causes addNewRow() to fail
    // const template = document.getElementById('new-item-template');
    // if (template) {
    //     template.classList.add('hidden');
    //     template.style.display = 'none';
    // }
}

function updateSummary(customBudget, customRealized) {
    const budgetInput = document.querySelector('input[name="budgeted_amount"]');
    const budgetValue = customBudget !== undefined ? parseFloat(customBudget) : (budgetInput ? parseFloat(getRawValue(budgetInput.value, window.FLOWGROUP_CONFIG.thousandSeparator, window.FLOWGROUP_CONFIG.decimalSeparator)) : 0);
    let totalEstimated = 0;
    let totalRealized = customRealized !== undefined ? parseFloat(customRealized) : 0;
    if (customRealized === undefined) {
        const rows = document.querySelectorAll('tr[id^="item-"]');
        rows.forEach(row => {
            const itemId = row.id.replace('item-', '');
            if (itemId !== 'NEW' && itemId !== 'new-item-template') {
                const amountInput = row.querySelector('input[data-field="amount"]');
                if (amountInput && amountInput.value) {
                    const amount = parseFloat(getRawValue(amountInput.value, window.FLOWGROUP_CONFIG.thousandSeparator, window.FLOWGROUP_CONFIG.decimalSeparator)) || 0;
                    totalEstimated += amount;
                    if (row.getAttribute('data-realized') === 'true') {
                        totalRealized += amount;
                    }
                }
            }
        });
    } else {
        const rows = document.querySelectorAll('tr[id^="item-"]');
        rows.forEach(row => {
            const itemId = row.id.replace('item-', '');
            if (itemId !== 'NEW' && itemId !== 'new-item-template') {
                const amountInput = row.querySelector('input[data-field="amount"]');
                if (amountInput && amountInput.value) {
                    const amount = parseFloat(getRawValue(amountInput.value, window.FLOWGROUP_CONFIG.thousandSeparator, window.FLOWGROUP_CONFIG.decimalSeparator)) || 0;
                    totalEstimated += amount;
                }
            }
        });
    }
    const estimatedSpan = document.getElementById('total-estimated');
    const realizedSpan = document.getElementById('total-realized');
    const remainingSpan = document.getElementById('total-remaining');
    if (estimatedSpan) {
        estimatedSpan.textContent = formatCurrency(totalEstimated, window.FLOWGROUP_CONFIG.currencySymbol, window.FLOWGROUP_CONFIG.thousandSeparator, window.FLOWGROUP_CONFIG.decimalSeparator);
    }
    if (realizedSpan) {
        realizedSpan.textContent = formatCurrency(totalRealized, window.FLOWGROUP_CONFIG.currencySymbol, window.FLOWGROUP_CONFIG.thousandSeparator, window.FLOWGROUP_CONFIG.decimalSeparator);
    }
    if (remainingSpan) {
        const remaining = budgetValue - totalRealized;
        remainingSpan.textContent = formatCurrency(remaining, window.FLOWGROUP_CONFIG.currencySymbol, window.FLOWGROUP_CONFIG.thousandSeparator, window.FLOWGROUP_CONFIG.decimalSeparator);
        const remainingContainer = remainingSpan.closest('.flex');
        if (remainingContainer) {
            if (remaining < 0) {
                remainingContainer.classList.remove('text-green-600', 'dark:text-green-400');
                remainingContainer.classList.add('text-red-600', 'dark:text-red-400');
            } else {
                remainingContainer.classList.remove('text-red-600', 'dark:text-red-400');
                remainingContainer.classList.add('text-green-600', 'dark:text-green-400');
            }
        }
    }

    // Totals row is now updated via backend calculation and WebSocket broadcasts
    // No need to calculate totals in JavaScript anymore
}

// Initialize mobile swipe and tap functionality for expense items
function initMobileExpenseFeatures() {
    'use strict';

    const isMobile = window.matchMedia('(max-width: 768px)').matches;

    if (!isMobile) {
        console.log('[MOBILE EXPENSE] Not mobile viewport, skipping mobile features');
        return; // Only run on mobile devices
    }

    console.log('[MOBILE EXPENSE] Initializing mobile features for expense items');
    const swipeableRows = document.querySelectorAll('.swipeable-row');
    console.log('[MOBILE EXPENSE] Found', swipeableRows.length, 'swipeable rows');

    swipeableRows.forEach(row => {
        // Skip if already initialized
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

        let startY = 0;
        let currentY = 0;
        let isDragMode = false; // true = vertical drag, false = horizontal swipe
        let isDecided = false; // se já decidimos o modo

        // Touch start
        row.addEventListener('touchstart', (e) => {
            // Se começou no drag handle, NÃO processar swipe
            const isDragHandle = e.target.closest('.drag-handle');
            if (isDragHandle) {
                return;
            }

            // Ignore if touching action buttons or check icon
            if (e.target.closest('.mobile-action-btn')) return;
            if (e.target.closest('.mobile-fixed-btn')) return;
            if (e.target.closest('.edit-save-icon')) return;

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

            if (e.target.closest('.mobile-action-btn')) return;
            if (e.target.closest('.mobile-fixed-btn')) return;
            if (e.target.closest('.edit-save-icon')) return;

            currentX = e.touches[0].clientX;
            currentY = e.touches[0].clientY;
            const deltaX = currentX - startX;
            const deltaY = currentY - startY;

            // In edit mode: allow swipe right to cancel
            if (row.dataset.mode === 'edit') {
                if (deltaX > 0) {
                    isDragging = true;
                    const translateX = Math.min(deltaX, 120);
                    row.style.transform = `translateX(${translateX}px)`;
                    row.style.transition = 'none';
                }
            } else {
                // In display mode: swipe left to reveal edit/delete, swipe right to reveal fixed button
                if (Math.abs(deltaX) > 10) {
                    isDragging = true;
                    if (deltaX < 0) {
                        // Swipe left - reveal edit/delete buttons
                        const translateX = Math.max(deltaX, -120);
                        row.style.transform = `translateX(${translateX}px)`;
                        row.style.transition = 'none';
                    } else {
                        // Swipe right - reveal fixed button
                        const translateX = Math.min(deltaX, 80);
                        row.style.transform = `translateX(${translateX}px)`;
                        row.style.transition = 'none';
                    }
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
                    console.log('[MOBILE EXPENSE SWIPE] Canceling edit mode for:', row.id);
                    // CRITICAL FIX: If it's the template, call cancelNewRow instead of toggleEditMode
                    if (row.id === 'new-item-template') {
                        window.cancelNewRow('new-item-template');
                    } else {
                        toggleEditMode(row.id, false);
                        // toggleEditMode already re-enables drag
                    }
                } else {
                    row.style.transform = 'translateX(0)';
                    // Still in edit mode, keep drag disabled
                }
            } else {
                // Check if row has revealed actions - if so, reset position instead of toggling realized
                const hasRevealedActions = row.classList.contains('actions-revealed') || row.classList.contains('fixed-revealed');

                // Tap detection for realized toggle - only if no revealed actions
                if (!isDragging && Math.abs(deltaX) < 10 && deltaTime < tapTimeThreshold) {
                    if (hasRevealedActions) {
                        // Row has revealed actions - reset position instead of toggling
                        console.log('[MOBILE EXPENSE TAP] Resetting position (actions revealed)');
                        row.style.transform = 'translateX(0)';
                        row.classList.remove('actions-revealed', 'fixed-revealed');
                        // CRITICAL FIX: Re-enable drag when returning to original position
                        row.setAttribute('draggable', 'true');
                    } else {
                        // No revealed actions - toggle realized
                        const rowId = row.id;
                        console.log('[MOBILE EXPENSE TAP] Toggling realized:', rowId);
                        toggleRealized(rowId);
                    }
                }
                // Swipe left to reveal edit/delete actions
                else if (deltaX < -swipeThreshold) {
                    row.style.transform = 'translateX(-120px)';
                    row.classList.add('actions-revealed');
                    row.classList.remove('fixed-revealed');
                    // CRITICAL FIX: Disable drag when swipe is revealed (allows buttons to work!)
                    row.setAttribute('draggable', 'false');
                }
                // Swipe right to reveal fixed button
                else if (deltaX > swipeThreshold) {
                    row.style.transform = 'translateX(80px)';
                    row.classList.add('fixed-revealed');
                    row.classList.remove('actions-revealed');
                    // CRITICAL FIX: Disable drag when swipe is revealed (allows fixed button to work!)
                    row.setAttribute('draggable', 'false');
                } else {
                    row.style.transform = 'translateX(0)';
                    row.classList.remove('actions-revealed', 'fixed-revealed');
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
            if (!row.contains(e.target) && (row.classList.contains('actions-revealed') || row.classList.contains('fixed-revealed'))) {
                row.style.transform = 'translateX(0)';
                row.classList.remove('actions-revealed', 'fixed-revealed');
                // CRITICAL FIX: Re-enable drag when returning to original position
                row.setAttribute('draggable', 'true');
            }
        }, { passive: true });
    });

    // Add change event listener to all expense date inputs to update display value
    const dateInputs = document.querySelectorAll('.date-input-field');
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
                console.log('[MOBILE EXPENSE DATE] Updated display value:', displayValue);
            }
        });
    });
}

// Initialize mobile features on page load
document.addEventListener('DOMContentLoaded', function() {
    initMobileExpenseFeatures();
});
