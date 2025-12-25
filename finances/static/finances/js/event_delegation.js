/**
 * Event Delegation Manager - Phase 3 Security Implementation
 *
 * Centralizes ALL event listeners to eliminate inline event handlers
 * This allows removal of 'unsafe-inline' from CSP
 *
 * Version: 1.0.0
 * Created: 2025-12-24
 * Part of: Security Phase 3 - CSP Hardening
 */

class EventDelegationManager {
    constructor() {
        this.init();
    }

    init() {
        // Click events (buttons, links, etc.)
        document.addEventListener('click', this.handleClick.bind(this));

        // Change events (selects, inputs)
        document.addEventListener('change', this.handleChange.bind(this));

        // Input events (real-time input)
        document.addEventListener('input', this.handleInput.bind(this));

        console.log('[EventDelegation] Manager initialized - Phase 3 active');
    }

    /**
     * Handle all click events using delegation
     */
    handleClick(event) {
        // Action buttons (edit, save, delete, cancel, etc.)
        const actionButton = event.target.closest('[data-action]');
        if (actionButton) {
            this.handleAction(actionButton, event);
            return;
        }

        // Modal buttons (open, close)
        const modalButton = event.target.closest('[data-modal-action]');
        if (modalButton) {
            this.handleModal(modalButton, event);
            return;
        }

        // Toggle buttons (realized status, active/inactive)
        const toggleButton = event.target.closest('[data-toggle]');
        if (toggleButton) {
            this.handleToggle(toggleButton, event);
            return;
        }
    }

    /**
     * Handle action buttons (edit, save, delete, cancel, etc.)
     */
    handleAction(button, event) {
        event.preventDefault();

        const action = button.dataset.action;
        const itemId = button.dataset.itemId;
        const type = button.dataset.type;
        const rowId = button.dataset.rowId;

        // Action mapping
        const actions = {
            // Income/Expense actions
            'edit': () => toggleEditMode(itemId, true),
            'save': () => saveItem(itemId),
            'delete': () => deleteItem(itemId),
            'cancel': () => toggleEditMode(itemId, false),

            // Balance actions (bank_reconciliation.html)
            'edit-balance': () => toggleEditBalance(rowId, true),
            'save-balance': () => saveBalance(rowId),
            'delete-balance': () => deleteBalance(itemId),
            'cancel-balance': () => toggleEditBalance(rowId, false),
            'add-balance': () => addNewBalance(),
            'cancel-new-balance': () => cancelNewBalance(),

            // Add new row
            'add-new-row': () => this.addNewRow(type),

            // Save new item
            'save-new-income': () => saveIncomeItem('new-income-template'),
            'cancel-new-income': () => cancelNewIncomeRow('new-income-template'),
            'save-new-expense': () => saveExpenseItem('new-expense-template'),
            'cancel-new-expense': () => cancelNewExpenseRow('new-expense-template'),

            // Alert for kids (read-only)
            'show-alert': () => alert(button.dataset.message),

            // Period actions
            'confirm-delete-period': () => confirmDeletePeriod(),

            // Update version
            'update-version': () => updateInstalledVersion(button.dataset.version),

            // Bank balance actions (bank_reconciliation.html)
            'edit-balance': () => toggleEditBalance(button.dataset.rowId, true),
            'save-balance': () => saveBalance(button.dataset.rowId),
            'cancel-balance': () => toggleEditBalance(button.dataset.rowId, false),
            'delete-balance': () => deleteBalance(button.dataset.itemId),
            'add-new-balance': () => addNewBalance(),
            'cancel-new-balance': () => cancelNewBalance(),

            // Password visibility toggle (password_reset_confirm.html)
            'toggle-password': () => {
                const targetId = button.dataset.target;
                togglePasswordVisibility(targetId, button);
            },

            // Offline/Setup page actions
            'retry-connection': () => retryConnection(),
            'reload-page': () => window.location.reload(),

            // FlowGroup actions
            'delete-flowgroup': () => deleteFlowGroup(),
            'history-back': () => history.back(),
            'toggle-flowgroup-recurring': () => toggleFlowGroupRecurring(),
            'toggle-kids-realized': () => {
                const currentState = button.dataset.currentState === 'true';
                toggleKidsGroupRealized(currentState);
            },
            'toggle-creditcard-closed': () => {
                const currentState = button.dataset.currentState === 'true';
                toggleCreditCardClosed(currentState);
            },
            'toggle-fixed': () => toggleTransactionFixed(button.dataset.itemId),
            'toggle-new-item-fixed': () => toggleNewItemFixed(button.dataset.itemId),
            'cancel-new-row': () => cancelNewRow(button.dataset.itemId),
            'add-new-row': () => addNewRow(),
        };

        const handler = actions[action];
        if (handler) {
            handler();
        } else {
            console.warn(`[EventDelegation] Unknown action: ${action}`);
        }
    }

    /**
     * Handle modal buttons (open, close)
     */
    handleModal(button, event) {
        event.preventDefault();

        const action = button.dataset.modalAction;
        const modalName = button.dataset.modal;

        const modals = {
            'create-period': {
                open: () => openCreatePeriodModal(),
                close: () => closeCreatePeriodModal()
            },
            'delete-period': {
                open: () => openDeletePeriodModal(),
                close: () => closeDeletePeriodModal()
            }
        };

        const modal = modals[modalName];
        if (modal && modal[action]) {
            modal[action]();
        } else {
            console.warn(`[EventDelegation] Unknown modal: ${modalName}, action: ${action}`);
        }
    }

    /**
     * Handle toggle buttons (realized status, etc.)
     */
    handleToggle(button, event) {
        event.preventDefault();

        const toggleType = button.dataset.toggle;
        const itemId = button.dataset.itemId;

        const toggles = {
            'income-realized': () => toggleIncomeRealized(itemId),
            'expense-realized': () => toggleExpenseRealized(itemId),
        };

        const handler = toggles[toggleType];
        if (handler) {
            handler();
        } else {
            console.warn(`[EventDelegation] Unknown toggle: ${toggleType}`);
        }
    }

    /**
     * Handle change events (selects, inputs)
     */
    handleChange(event) {
        const element = event.target.closest('[data-change-action]');
        if (!element) return;

        const action = element.dataset.changeAction;
        const value = element.value;

        const actions = {
            'filter-period': () => filterByPeriod(value),
            'filter-member': () => filterByMember(value),
            'filter-flowgroup': () => filterByFlowGroup(value),
        };

        const handler = actions[action];
        if (handler) {
            handler();
        } else {
            console.warn(`[EventDelegation] Unknown change action: ${action}`);
        }
    }

    /**
     * Handle input events (real-time input)
     */
    handleInput(event) {
        const element = event.target.closest('[data-input-action]');
        if (!element) return;

        const action = element.dataset.inputAction;
        const value = element.value;

        const actions = {
            'search': () => performSearch(value),
            'filter': () => performFilter(value),
        };

        const handler = actions[action];
        if (handler) {
            handler();
        }
    }

    /**
     * Add new row (income or expense)
     */
    addNewRow(type) {
        if (type === 'income') {
            addNewIncomeRow();
        } else if (type === 'expense') {
            addNewExpenseRow();
        } else {
            console.warn(`[EventDelegation] Unknown row type: ${type}`);
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.eventDelegation = new EventDelegationManager();
    console.log('[EventDelegation] Phase 3 - Inline handlers eliminated');
});
