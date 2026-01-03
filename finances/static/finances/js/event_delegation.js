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
        const itemId = button.dataset.itemId; // For backwards compatibility
        const type = button.dataset.type;
        const rowId = button.dataset.rowId || itemId; // Prefer rowId, fallback to itemId

        // Action mapping
        const actions = {
            // Income/Expense actions
            'edit': () => {
                if (typeof window.toggleEditMode === 'function') {
                    window.toggleEditMode(rowId, true);
                } else {
                    console.error('[EventDelegation] window.toggleEditMode is not defined');
                }
            },
            'save': () => {
                if (typeof window.saveItem === 'function') {
                    window.saveItem(rowId);
                } else {
                    console.error('[EventDelegation] window.saveItem is not defined');
                }
            },
            'delete': () => {
                if (typeof window.deleteItem === 'function') {
                    window.deleteItem(rowId);
                } else {
                    console.error('[EventDelegation] window.deleteItem is not defined');
                }
            },
            'cancel': () => {
                if (typeof window.toggleEditMode === 'function') {
                    window.toggleEditMode(rowId, false);
                } else {
                    console.error('[EventDelegation] window.toggleEditMode is not defined');
                }
            },

            // Balance actions (bank_reconciliation.html)
            'edit-balance': () => {
                if (typeof window.toggleEditBalance === 'function') {
                    window.toggleEditBalance(rowId, true);
                } else {
                    console.error('[EventDelegation] window.toggleEditBalance is not defined');
                }
            },
            'save-balance': () => {
                if (typeof window.saveBalance === 'function') {
                    window.saveBalance(rowId);
                } else {
                    console.error('[EventDelegation] window.saveBalance is not defined');
                }
            },
            'delete-balance': () => {
                if (typeof window.deleteBalance === 'function') {
                    window.deleteBalance(itemId);
                } else {
                    console.error('[EventDelegation] window.deleteBalance is not defined');
                }
            },
            'cancel-balance': () => {
                if (typeof window.toggleEditBalance === 'function') {
                    window.toggleEditBalance(rowId, false);
                } else {
                    console.error('[EventDelegation] window.toggleEditBalance is not defined');
                }
            },
            'add-balance': () => {
                if (typeof window.addNewBalance === 'function') {
                    window.addNewBalance();
                } else {
                    console.error('[EventDelegation] window.addNewBalance is not defined');
                }
            },
            'cancel-new-balance': () => {
                if (typeof window.cancelNewBalance === 'function') {
                    window.cancelNewBalance();
                } else {
                    console.error('[EventDelegation] window.cancelNewBalance is not defined');
                }
            },

            // Add new row
            'add-new-row': () => this.addNewRow(type),

            // Save new item
            'save-new-income': () => {
                if (typeof window.saveIncomeItem === 'function') {
                    window.saveIncomeItem('new-income-template');
                } else {
                    console.error('[EventDelegation] window.saveIncomeItem is not defined');
                }
            },
            'cancel-new-income': () => {
                if (typeof window.cancelNewIncomeRow === 'function') {
                    window.cancelNewIncomeRow('new-income-template');
                } else {
                    console.error('[EventDelegation] window.cancelNewIncomeRow is not defined');
                }
            },
            'save-new-expense': () => {
                if (typeof window.saveItem === 'function') {
                    window.saveItem('new-item-template');
                } else {
                    console.error('[EventDelegation] window.saveItem is not defined');
                }
            },
            'cancel-new-expense': () => {
                if (typeof window.cancelNewRow === 'function') {
                    window.cancelNewRow('new-item-template');
                } else {
                    console.error('[EventDelegation] window.cancelNewRow is not defined');
                }
            },

            // Alert for kids (read-only)
            'show-alert': () => alert(button.dataset.message),

            // Period actions
            'confirm-delete-period': () => {
                if (typeof window.confirmDeletePeriod === 'function') {
                    window.confirmDeletePeriod();
                } else {
                    console.error('[EventDelegation] window.confirmDeletePeriod is not defined');
                }
            },

            // Update version
            'update-version': () => {
                if (typeof window.updateInstalledVersion === 'function') {
                    window.updateInstalledVersion(button.dataset.version);
                } else {
                    console.error('[EventDelegation] window.updateInstalledVersion is not defined');
                }
            },

            // Password visibility toggle (password_reset_confirm.html)
            'toggle-password': () => {
                const targetId = button.dataset.target;
                if (typeof window.togglePasswordVisibility === 'function') {
                    window.togglePasswordVisibility(targetId, button);
                } else {
                    console.error('[EventDelegation] window.togglePasswordVisibility is not defined');
                }
            },

            // Offline/Setup page actions
            'retry-connection': () => {
                if (typeof window.retryConnection === 'function') {
                    window.retryConnection();
                } else {
                    console.error('[EventDelegation] window.retryConnection is not defined');
                }
            },
            'reload-page': () => window.location.reload(),

            // FlowGroup actions
            'delete-flowgroup': () => {
                if (typeof window.deleteFlowGroup === 'function') {
                    window.deleteFlowGroup();
                } else {
                    console.error('[EventDelegation] window.deleteFlowGroup is not defined');
                }
            },
            'history-back': () => history.back(),
            'toggle-flowgroup-recurring': () => {
                if (typeof window.toggleFlowGroupRecurring === 'function') {
                    window.toggleFlowGroupRecurring();
                } else {
                    console.error('[EventDelegation] window.toggleFlowGroupRecurring is not defined');
                }
            },
            'toggle-kids-realized': () => {
                const currentState = button.dataset.currentState === 'true';
                if (typeof window.toggleKidsGroupRealized === 'function') {
                    window.toggleKidsGroupRealized(currentState);
                } else {
                    console.error('[EventDelegation] window.toggleKidsGroupRealized is not defined');
                }
            },
            'toggle-creditcard-closed': () => {
                const currentState = button.dataset.currentState === 'true';
                if (typeof window.toggleCreditCardClosed === 'function') {
                    window.toggleCreditCardClosed(currentState);
                } else {
                    console.error('[EventDelegation] window.toggleCreditCardClosed is not defined');
                }
            },
            'toggle-fixed': () => {
                if (typeof window.toggleTransactionFixed === 'function') {
                    window.toggleTransactionFixed(button.dataset.itemId);
                } else {
                    console.error('[EventDelegation] window.toggleTransactionFixed is not defined');
                }
            },
            'toggle-transaction-fixed': () => {
                const rowId = button.dataset.rowId || button.closest('tr')?.id;
                if (typeof window.toggleTransactionFixed === 'function') {
                    window.toggleTransactionFixed(rowId);
                } else {
                    console.error('[EventDelegation] window.toggleTransactionFixed is not defined');
                }
            },
            'toggle-new-item-fixed': () => {
                if (typeof window.toggleNewItemFixed === 'function') {
                    window.toggleNewItemFixed(button.dataset.itemId);
                } else {
                    console.error('[EventDelegation] window.toggleNewItemFixed is not defined');
                }
            },
            'cancel-new-row': () => {
                if (typeof window.cancelNewRow === 'function') {
                    window.cancelNewRow(button.dataset.itemId);
                } else {
                    console.error('[EventDelegation] window.cancelNewRow is not defined');
                }
            },
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
        const currentState = button.dataset.currentState === 'true';

        const toggles = {
            'income-realized': () => {
                if (typeof window.toggleIncomeRealized === 'function') {
                    window.toggleIncomeRealized(itemId);
                } else {
                    console.error('[EventDelegation] window.toggleIncomeRealized is not defined');
                }
            },
            'expense-realized': () => {
                if (typeof window.toggleExpenseRealized === 'function') {
                    window.toggleExpenseRealized(itemId);
                } else {
                    console.error('[EventDelegation] window.toggleExpenseRealized is not defined');
                }
            },
            'realized': () => {
                if (typeof window.toggleRealized === 'function') {
                    window.toggleRealized(itemId, currentState);
                } else {
                    console.error('[EventDelegation] window.toggleRealized is not defined');
                }
            },
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
            'toggle-delete-consent': () => this.toggleDeleteButton(element),
            'toggle-reconciliation-mode': () => this.toggleReconciliationMode(element.checked),
            'handle-shared-change': () => this.handleSharedChange(),
            'handle-kids-change': () => this.handleKidsChange(),
            'handle-creditcard-change': () => this.handleCreditCardChange(),
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
            if (typeof window.addNewIncomeRow === 'function') {
                window.addNewIncomeRow();
            } else {
                console.error('[EventDelegation] window.addNewIncomeRow is not defined');
            }
        } else if (type === 'expense') {
            if (typeof window.addNewRow === 'function') {
                window.addNewRow();
            } else {
                console.error('[EventDelegation] window.addNewRow is not defined');
            }
        } else {
            console.warn(`[EventDelegation] Unknown row type: ${type}`);
        }
    }

    /**
     * Toggle delete button enable/disable (base.html delete period modal)
     */
    toggleDeleteButton(checkbox) {
        const deleteBtn = document.getElementById('confirmDeleteBtn');
        if (!deleteBtn) return;

        if (checkbox.checked) {
            deleteBtn.disabled = false;
            deleteBtn.style.backgroundColor = '#ef4444';
            deleteBtn.style.color = '#ffffff';
            deleteBtn.style.cursor = 'pointer';
        } else {
            deleteBtn.disabled = true;
            deleteBtn.style.backgroundColor = '#d1d5db';
            deleteBtn.style.color = '#6b7280';
            deleteBtn.style.cursor = 'not-allowed';
        }
    }

    /**
     * Toggle bank reconciliation mode (general vs detailed)
     */
    toggleReconciliationMode(isChecked) {
        const urlParams = new URLSearchParams(window.location.search);
        const period = urlParams.get('period') || '';
        const mode = isChecked ? 'detailed' : 'general';
        window.location.href = `/bank-reconciliation/?period=${period}&mode=${mode}`;
    }

    /**
     * Handle shared group checkbox change (FlowGroup.html)
     */
    handleSharedChange() {
        const sharedCheckbox = document.getElementById('id_is_shared');
        const kidsCheckbox = document.getElementById('id_is_kids_group');
        const membersContainer = document.getElementById('members-selection-container');

        if (!sharedCheckbox || !membersContainer) return;

        if (sharedCheckbox.checked) {
            if (kidsCheckbox && kidsCheckbox.checked) {
                membersContainer.style.display = 'none';
            } else {
                membersContainer.style.display = 'flex';
            }
        } else {
            membersContainer.style.display = 'none';
        }
    }

    /**
     * Handle kids group checkbox change (FlowGroup.html)
     */
    handleKidsChange() {
        const kidsCheckbox = document.getElementById('id_is_kids_group');
        const sharedCheckbox = document.getElementById('id_is_shared');
        const childrenContainer = document.getElementById('children-selection-container');
        const membersContainer = document.getElementById('members-selection-container');

        if (!kidsCheckbox || !childrenContainer) return;

        if (kidsCheckbox.checked) {
            childrenContainer.style.display = 'flex';
            if (sharedCheckbox) {
                sharedCheckbox.checked = true;
                membersContainer.style.display = 'none';
            }
        } else {
            childrenContainer.style.display = 'none';
            if (sharedCheckbox && sharedCheckbox.checked) {
                membersContainer.style.display = 'flex';
            }
        }
    }

    /**
     * Handle credit card checkbox change (FlowGroup.html)
     */
    handleCreditCardChange() {
        const creditCardCheckbox = document.getElementById('id_is_credit_card');
        const closedDateContainer = document.getElementById('credit-card-closed-date-container');

        if (!creditCardCheckbox || !closedDateContainer) return;

        if (creditCardCheckbox.checked) {
            closedDateContainer.style.display = 'block';
        } else {
            closedDateContainer.style.display = 'none';
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.eventDelegation = new EventDelegationManager();
    console.log('[EventDelegation] Phase 3 - Inline handlers eliminated');
});
