/**
 * Real-time Updates for Dashboard
 * Handles WebSocket broadcasts to update the income transactions list
 */
(function() {
    'use strict';

    // Dashboard Real-time Updates Namespace
    window.DashboardRealtime = {
        /**
         * Add new transaction to the list
         */
        addTransaction: function(transactionData) {
            console.log('[Dashboard RT] Adding new transaction:', transactionData);

            // Check if transaction is income type (since dashboard shows income)
            if (!transactionData.is_income) {
                console.log('[Dashboard RT] Transaction is not income, skipping');
                return;
            }

            const tbody = document.getElementById('income-items-body');
            if (!tbody) {
                console.warn('[Dashboard RT] Income tbody not found');
                return;
            }

            // Check if transaction already exists (avoid duplicates)
            const existingRow = document.getElementById(`income-item-${transactionData.id}`);
            if (existingRow) {
                console.log('[Dashboard RT] Transaction already exists, updating instead');
                this.updateTransaction(transactionData);
                return;
            }

            // Create new row
            const newRow = this._createTransactionRow(transactionData);

            // Insert at the beginning of tbody
            tbody.insertBefore(newRow, tbody.firstChild);

            // CRITICAL FIX: Re-initialize mobile features for the new row
            if (typeof window.initMobileIncomeFeatures === 'function') {
                window.initMobileIncomeFeatures();
                console.log('[Dashboard RT] Mobile features re-initialized for new row');
            }

            // Add fade-in animation
            setTimeout(() => {
                newRow.style.transition = 'background-color 0.5s ease';
                newRow.style.backgroundColor = '';
            }, 100);

            console.log('[Dashboard RT] Transaction added successfully');
        },

        /**
         * Update existing transaction
         */
        updateTransaction: function(transactionData) {
            const row = document.getElementById(`income-item-${transactionData.id}`);
            if (!row) {
                return;
            }

            try {
                // Update description
                const descDisplay = row.querySelector('.cell-description-display');
                if (descDisplay) {
                    descDisplay.textContent = transactionData.description;
                }
                const descInput = row.querySelector('input[data-field="description"]');
                if (descInput) {
                    descInput.value = transactionData.description;
                }

                // Update date
                if (transactionData.date) {
                    const dateDisplay = row.querySelector('.cell-date-display');
                    if (dateDisplay) {
                        const dateObj = new Date(transactionData.date);
                        const day = String(dateObj.getDate()).padStart(2, '0');
                        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
                        dateDisplay.textContent = `${day}/${month}`;
                    }
                    const dateInput = row.querySelector('input[data-field="date"]');
                    if (dateInput) {
                        dateInput.value = transactionData.date;
                    }
                    row.dataset.date = transactionData.date;
                }

                // Update amount
                if (transactionData.amount) {
                    const amountDisplay = row.querySelector('.cell-amount-display');
                    if (amountDisplay) {
                        const formattedAmount = window.RealtimeUI.utils.formatCurrency(transactionData.amount);
                        amountDisplay.textContent = formattedAmount;
                    }
                    const amountInput = row.querySelector('input[data-field="amount"]');
                    if (amountInput && typeof formatAmountForInput === 'function') {
                        amountInput.value = formatAmountForInput(transactionData.amount);
                    } else if (amountInput) {
                        amountInput.value = transactionData.amount;
                    }
                    row.dataset.amount = transactionData.amount;
                }

                // Update is_fixed
                if (typeof transactionData.is_fixed !== 'undefined') {
                    row.dataset.isFixed = transactionData.is_fixed ? 'true' : 'false';
                }

                // Update realized status
                if (typeof transactionData.realized !== 'undefined') {
                    row.dataset.realized = transactionData.realized ? 'true' : 'false';

                    // Update row background class
                    if (transactionData.realized) {
                        row.classList.remove('row-not-realized-income');
                        row.classList.add('row-realized-income');
                    } else {
                        row.classList.remove('row-realized-income');
                        row.classList.add('row-not-realized-income');
                    }

                    // Update toggle button
                    const toggleBtn = row.querySelector('.income-realized-toggle');
                    if (toggleBtn) {
                        if (transactionData.realized) {
                            toggleBtn.classList.add('bg-green-500');
                            toggleBtn.classList.remove('bg-gray-300', 'dark:bg-gray-600');
                        } else {
                            toggleBtn.classList.remove('bg-green-500');
                            toggleBtn.classList.add('bg-gray-300', 'dark:bg-gray-600');
                        }

                        const toggleSpan = toggleBtn.querySelector('span');
                        if (toggleSpan) {
                            if (transactionData.realized) {
                                toggleSpan.classList.add('translate-x-4');
                            } else {
                                toggleSpan.classList.remove('translate-x-4');
                            }
                        }
                    }

                    // Update amount cell color (4th column)
                    const amountCell = row.querySelector('td:nth-child(4)');
                    if (amountCell) {
                        if (transactionData.realized) {
                            amountCell.classList.add('text-green-600', 'dark:text-green-500');
                            amountCell.classList.remove('text-gray-400', 'dark:text-gray-500');
                        } else {
                            amountCell.classList.remove('text-green-600', 'dark:text-green-500');
                            amountCell.classList.add('text-gray-400', 'dark:text-gray-500');
                        }
                    }
                }

                // Highlight the updated row to show it changed
                if (window.RealtimeUI && window.RealtimeUI.utils && window.RealtimeUI.utils.highlightElement) {
                    window.RealtimeUI.utils.highlightElement(row, 2000);
                } else {
                    row.style.backgroundColor = 'rgba(250, 204, 21, 0.3)';
                    setTimeout(() => {
                        row.style.backgroundColor = '';
                    }, 2000);
                }

                // Update balance sheet, key metrics, and charts
                if (typeof updateBalanceSheet === 'function') {
                    updateBalanceSheet();
                }
            } catch (error) {
                console.error('[Dashboard RT] Error updating transaction:', error);
            }
        },

        /**
         * Remove transaction from the list
         */
        removeTransaction: function(transactionId) {
            console.log('[Dashboard RT] Removing transaction:', transactionId);

            const row = document.getElementById(`income-item-${transactionId}`);
            if (!row) {
                console.warn('[Dashboard RT] Transaction row not found');
                return;
            }

            // Fade out animation
            row.style.transition = 'opacity 0.3s ease';
            row.style.opacity = '0';

            setTimeout(() => {
                if (row.parentNode) {
                    row.parentNode.removeChild(row);
                    console.log('[Dashboard RT] Transaction removed successfully');
                }
            }, 300);
        },

        /**
         * Create a new transaction row element
         * @private
         */
        _createTransactionRow: function(data) {
            const tr = document.createElement('tr');
            tr.id = `income-item-${data.id}`;
            tr.dataset.itemId = data.id;
            tr.dataset.mode = 'display';
            tr.dataset.realized = data.realized ? 'true' : 'false';
            tr.dataset.isFixed = data.is_fixed ? 'true' : 'false';
            tr.dataset.date = data.date;
            tr.dataset.amount = data.amount;
            tr.className = `swipeable-row-income ${data.realized ? 'row-realized-income' : 'row-not-realized-income'} hover:bg-slate-50 dark:hover:bg-gray-700/50`;
            tr.style.backgroundColor = 'rgba(34, 197, 94, 0.1)'; // Initial highlight

            // Format date for display
            let dateDisplay = '';
            if (data.date) {
                const dateObj = new Date(data.date);
                const day = String(dateObj.getDate()).padStart(2, '0');
                const month = String(dateObj.getMonth() + 1).padStart(2, '0');
                dateDisplay = `${day}/${month}`;
            }

            // Format amount
            const formattedAmount = window.RealtimeUI.utils.formatCurrency(data.amount);

            // SECURITY FIX (Phase 2 - Enhanced): Use createElement() to avoid innerHTML completely
            // This is the SAFEST approach - no string interpolation, no XSS risk
            const itemId = `income-item-${data.id}`;

            // Helper function to create elements safely
            function createEl(tag, classes, content) {
                const el = document.createElement(tag);
                if (classes) el.className = classes;
                if (content) el.textContent = content;
                return el;
            }

            // TD 1: Drag handle
            const td1 = createEl('td', 'px-2 py-4 text-center drag-handle-cell-income');
            td1.dataset.rowId = itemId;
            const dragIcon = createEl('span', 'material-symbols-outlined text-gray-400 dark:text-gray-500 drag-handle-income cursor-grab active:cursor-grabbing', 'drag_indicator');
            const saveBtn = document.createElement('button');
            saveBtn.type = 'button';
            saveBtn.className = 'edit-save-icon-income';
            saveBtn.style.display = 'none';
            saveBtn.onclick = () => saveItem(itemId);
            saveBtn.appendChild(createEl('span', 'material-symbols-outlined text-green-500 text-2xl', 'check_circle'));
            td1.appendChild(dragIcon);
            td1.appendChild(saveBtn);

            // TD 2: Description
            const td2 = createEl('td', 'py-3 px-3 text-sm text-[#0d171b] dark:text-white');
            const descDisplay = createEl('div', 'cell-description-display');
            descDisplay.textContent = data.description;  // SAFE
            const descEdit = createEl('div', 'cell-description-edit hidden');
            const descInput = document.createElement('input');
            descInput.type = 'text';
            descInput.dataset.field = 'description';
            descInput.className = 'w-full border-b border-primary bg-transparent focus:outline-none focus:ring-0 text-xs p-1';
            descInput.value = data.description;  // SAFE
            descEdit.appendChild(descInput);
            td2.appendChild(descDisplay);
            td2.appendChild(descEdit);

            // TD 3: Date
            const td3 = createEl('td', 'py-3 px-2 text-xs text-gray-500 dark:text-gray-400 text-center');
            const dateDisplayDiv = createEl('div', 'cell-date-display');
            dateDisplayDiv.textContent = dateDisplay;  // SAFE
            const dateEdit = createEl('div', 'cell-date-edit hidden');
            const dateInput = document.createElement('input');
            dateInput.type = 'date';
            dateInput.dataset.field = 'date';
            dateInput.className = 'w-full border-b border-primary dark:text-white dark:bg-gray-800 bg-transparent focus:outline-none focus:ring-0 text-xs p-1 date-input-field-income';
            dateInput.value = data.date;  // SAFE
            dateEdit.appendChild(dateInput);
            td3.appendChild(dateDisplayDiv);
            td3.appendChild(dateEdit);

            // TD 4: Amount + Mobile Actions
            const td4 = createEl('td', `py-3 px-3 text-sm text-right ${data.realized ? 'text-green-600 dark:text-green-500' : 'text-gray-400 dark:text-gray-500'} amount-cell-with-actions`);
            const amountDisplay = createEl('div', 'cell-amount-display');
            amountDisplay.textContent = formattedAmount;  // SAFE
            const amountEdit = createEl('div', 'cell-amount-edit hidden');
            const amountInput = document.createElement('input');
            amountInput.type = 'text';
            amountInput.inputMode = 'decimal';
            amountInput.dataset.field = 'amount';
            amountInput.className = 'w-20 border-b border-primary bg-transparent focus:outline-none focus:ring-0 text-xs text-right p-1';
            amountInput.value = data.amount;  // SAFE
            amountEdit.appendChild(amountInput);

            const mobileActions = createEl('div', 'mobile-actions-btns-income');
            const mobileEditBtn = document.createElement('button');
            mobileEditBtn.type = 'button';
            mobileEditBtn.className = 'mobile-action-btn-income edit-btn-income';
            mobileEditBtn.onclick = () => toggleEditMode(itemId, true);
            mobileEditBtn.appendChild(createEl('span', 'material-symbols-outlined', 'edit'));
            const mobileDeleteBtn = document.createElement('button');
            mobileDeleteBtn.type = 'button';
            mobileDeleteBtn.className = 'mobile-action-btn-income delete-btn-income';
            mobileDeleteBtn.onclick = () => deleteItem(itemId);
            mobileDeleteBtn.appendChild(createEl('span', 'material-symbols-outlined', 'delete'));
            mobileActions.appendChild(mobileEditBtn);
            mobileActions.appendChild(mobileDeleteBtn);

            td4.appendChild(amountDisplay);
            td4.appendChild(amountEdit);
            td4.appendChild(mobileActions);

            // TD 5: Realized Toggle
            const td5 = createEl('td', 'py-3 px-2 text-center mobile-hide-column');
            const toggleBtn = document.createElement('button');
            toggleBtn.type = 'button';
            toggleBtn.onclick = () => toggleIncomeRealized(itemId);
            toggleBtn.className = `income-realized-toggle relative inline-block w-10 h-6 transition duration-200 ease-in-out rounded-full cursor-pointer ${data.realized ? 'bg-green-500' : 'bg-gray-300 dark:bg-gray-600'}`;
            toggleBtn.appendChild(createEl('span', `absolute left-1 top-1 inline-block w-4 h-4 transition-transform duration-200 ease-in-out transform bg-white rounded-full ${data.realized ? 'translate-x-4' : ''}`));
            td5.appendChild(toggleBtn);

            // TD 6: Desktop Actions
            const td6 = createEl('td', 'px-2 py-3 text-center whitespace-nowrap mobile-hide-column');
            const actionsDisplay = createEl('div', 'actions-display flex justify-center gap-1');
            const editBtn = document.createElement('button');
            editBtn.type = 'button';
            editBtn.className = 'p-1 text-slate-500 hover:text-primary';
            editBtn.onclick = () => toggleEditMode(itemId, true);
            editBtn.appendChild(createEl('span', 'material-symbols-outlined text-lg', 'edit'));
            const deleteBtn = document.createElement('button');
            deleteBtn.type = 'button';
            deleteBtn.className = 'p-1 text-slate-500 hover:text-red-500';
            deleteBtn.onclick = () => deleteItem(itemId);
            deleteBtn.appendChild(createEl('span', 'material-symbols-outlined text-lg', 'delete'));
            actionsDisplay.appendChild(editBtn);
            actionsDisplay.appendChild(deleteBtn);

            const actionsEdit = createEl('div', 'actions-edit hidden flex justify-center gap-1');
            const saveBtn2 = document.createElement('button');
            saveBtn2.type = 'button';
            saveBtn2.className = 'p-1 text-primary hover:text-primary/80';
            saveBtn2.onclick = () => saveItem(itemId);
            saveBtn2.appendChild(createEl('span', 'material-symbols-outlined text-lg', 'check'));
            const cancelBtn = document.createElement('button');
            cancelBtn.type = 'button';
            cancelBtn.className = 'p-1 text-slate-500 hover:text-red-500';
            cancelBtn.onclick = () => toggleEditMode(itemId, false);
            cancelBtn.appendChild(createEl('span', 'material-symbols-outlined text-lg', 'close'));
            actionsEdit.appendChild(saveBtn2);
            actionsEdit.appendChild(cancelBtn);

            td6.appendChild(actionsDisplay);
            td6.appendChild(actionsEdit);

            // Assemble the row
            tr.appendChild(td1);
            tr.appendChild(td2);
            tr.appendChild(td3);
            tr.appendChild(td4);
            tr.appendChild(td5);
            tr.appendChild(td6);

            return tr;
        },

        /**
         * Add new FlowGroup to the Expense Groups table
         */
        addFlowGroup: function(flowgroupData) {
            console.log('[Dashboard RT] Adding new FlowGroup:', flowgroupData);

            const tbody = document.getElementById('expense-groups-tbody');
            if (!tbody) {
                console.warn('[Dashboard RT] Expense groups tbody not found');
                return;
            }

            // Check if FlowGroup already exists (avoid duplicates)
            const existingRow = tbody.querySelector(`tr[data-group-id="${flowgroupData.id}"]`);
            if (existingRow) {
                console.log('[Dashboard RT] FlowGroup already exists, updating instead');
                this.updateFlowGroup(flowgroupData);
                return;
            }

            // Create new row (simplified version - real implementation would match template exactly)
            const newRow = document.createElement('tr');
            newRow.dataset.groupId = flowgroupData.id;
            newRow.dataset.order = flowgroupData.order || 0;
            newRow.dataset.accessible = 'true';
            newRow.className = 'draggable-row cursor-default hover:bg-gray-50 dark:hover:bg-gray-700/30 group-row-clickable';
            newRow.draggable = true;

            const currencySymbol = window.currencySymbol || 'R$';
            const estimatedFormatted = window.RealtimeUI.utils.formatCurrency(flowgroupData.budgeted_amount || '0.00');
            const realizedFormatted = window.RealtimeUI.utils.formatCurrency('0.00');

            // SECURITY FIX (Phase 2 - Enhanced): Use createElement() to avoid innerHTML completely
            // No string interpolation = No XSS risk

            // Helper function (same as above)
            function createEl(tag, classes, content) {
                const el = document.createElement(tag);
                if (classes) el.className = classes;
                if (content) el.textContent = content;
                return el;
            }

            // TD 1: Drag handle
            const td1 = createEl('td', 'px-2 py-4 text-center drag-handle-cell');
            td1.appendChild(createEl('span', 'material-symbols-outlined text-gray-400 dark:text-gray-500 drag-handle cursor-grab active:cursor-grabbing', 'drag_indicator'));

            // TD 2: FlowGroup Name
            const td2 = createEl('td', 'py-4 px-4 text-sm text-[#0d171b] dark:text-white');
            const flexCol = createEl('div', 'flex flex-col gap-1');
            const flexRow = createEl('div', 'flex items-center gap-2');
            const nameSpan = createEl('span');
            nameSpan.textContent = flowgroupData.name;  // SAFE - prevents XSS
            flexRow.appendChild(nameSpan);
            flexCol.appendChild(flexRow);
            td2.appendChild(flexCol);

            // TD 3: Estimated Amount
            const td3 = createEl('td', 'py-4 px-4 text-sm text-gray-500 dark:text-gray-400 text-right group-estimated');
            td3.dataset.value = '0.00';
            const estimatedSpan = createEl('span');
            estimatedSpan.textContent = estimatedFormatted;  // SAFE
            td3.appendChild(estimatedSpan);

            // TD 4: Realized Amount
            const td4 = createEl('td', 'py-4 px-4 text-sm text-red-600 dark:text-red-500 text-right group-realized');
            td4.dataset.value = '0.00';
            const realizedSpan = createEl('span');
            realizedSpan.textContent = realizedFormatted;  // SAFE
            td4.appendChild(realizedSpan);

            // Assemble the row
            newRow.appendChild(td1);
            newRow.appendChild(td2);
            newRow.appendChild(td3);
            newRow.appendChild(td4);

            // Insert at the end (before "empty" message row if exists)
            const emptyRow = tbody.querySelector('tr td[colspan]');
            if (emptyRow) {
                emptyRow.parentElement.remove();
            }
            tbody.appendChild(newRow);

            // Add highlight animation
            if (window.RealtimeUI && window.RealtimeUI.utils && window.RealtimeUI.utils.highlightElement) {
                window.RealtimeUI.utils.highlightElement(newRow, 2000);
            }

            // Update balance sheet
            if (typeof updateBalanceSheet === 'function') {
                updateBalanceSheet();
            }

            // Update pie chart
            if (typeof updatePieChart === 'function') {
                updatePieChart();
            }

            console.log('[Dashboard RT] FlowGroup added successfully');
        },

        /**
         * Update existing FlowGroup in the Expense Groups table
         */
        updateFlowGroup: function(flowgroupData) {
            console.log('[Dashboard RT] Updating FlowGroup:', flowgroupData);

            const row = document.querySelector(`tr[data-group-id="${flowgroupData.id}"]`);
            if (!row) {
                console.log('[Dashboard RT] FlowGroup row not found in current view (may be in different period or no access)');
                return;
            }

            try {
                // Update name (2nd column)
                const nameCell = row.querySelector('td:nth-child(2) span');
                if (nameCell) {
                    nameCell.textContent = flowgroupData.name;
                }

                // Check for budget warning
                const budgetedAmount = parseFloat(flowgroupData.budgeted_amount) || 0;
                const totalEstimated = parseFloat(flowgroupData.total_estimated) || 0;
                const hasBudgetWarning = totalEstimated > budgetedAmount;

                // Update estimated (3rd column) with budget warning logic
                const estimatedCell = row.querySelector('.group-estimated');
                if (estimatedCell) {
                    // Show budgeted_amount normally, or total_estimated if over budget
                    const displayValue = hasBudgetWarning ? flowgroupData.total_estimated : flowgroupData.budgeted_amount;
                    const formattedEstimated = window.RealtimeUI.utils.formatCurrency(displayValue || '0.00');
                    estimatedCell.textContent = formattedEstimated;
                    estimatedCell.dataset.value = displayValue || '0.00';

                    // Update CSS classes for budget warning
                    estimatedCell.classList.remove('text-gray-500', 'dark:text-gray-400', 'text-yellow-600', 'dark:text-yellow-500', 'font-semibold');
                    if (hasBudgetWarning) {
                        estimatedCell.classList.add('text-yellow-600', 'dark:text-yellow-500', 'font-semibold');
                    } else {
                        estimatedCell.classList.add('text-gray-500', 'dark:text-gray-400');
                    }
                }

                // Update or add budget warning message
                const nameContainer = row.querySelector('td:nth-child(2) .flex.flex-col');
                if (nameContainer) {
                    // Remove existing warning if present
                    const existingWarning = nameContainer.querySelector('.text-xs.text-yellow-600');
                    if (existingWarning) {
                        existingWarning.remove();
                    }

                    // Add warning if over budget
                    if (hasBudgetWarning) {
                        const warningDiv = document.createElement('div');
                        warningDiv.className = 'text-xs text-yellow-600 dark:text-yellow-400 font-medium';
                        warningDiv.textContent = 'window.DASHBOARD_CONFIG.i18n.overBudget';
                        nameContainer.appendChild(warningDiv);
                    }
                }

                // Update realized (4th column)
                const realizedCell = row.querySelector('.group-realized');
                if (realizedCell) {
                    const formattedRealized = window.RealtimeUI.utils.formatCurrency(flowgroupData.total_realized || '0.00');
                    realizedCell.textContent = formattedRealized;
                    realizedCell.dataset.value = flowgroupData.total_realized || '0.00';
                }

                // Highlight the updated row
                if (window.RealtimeUI && window.RealtimeUI.utils && window.RealtimeUI.utils.highlightElement) {
                    window.RealtimeUI.utils.highlightElement(row, 2000);
                }

                // Update balance sheet
                if (typeof updateBalanceSheet === 'function') {
                    updateBalanceSheet();
                }

                // Update pie chart
                if (typeof updatePieChart === 'function') {
                    updatePieChart();
                }
            } catch (error) {
                console.error('[Dashboard RT] Error updating FlowGroup:', error);
            }
        },

        /**
         * Remove FlowGroup from the Expense Groups table
         */
        removeFlowGroup: function(flowgroupId) {
            console.log('[Dashboard RT] Removing FlowGroup:', flowgroupId);

            const row = document.querySelector(`tr[data-group-id="${flowgroupId}"]`);
            if (!row) {
                console.warn('[Dashboard RT] FlowGroup row not found');
                return;
            }

            // Fade out animation
            row.style.transition = 'opacity 0.3s ease';
            row.style.opacity = '0';

            setTimeout(() => {
                if (row.parentNode) {
                    row.parentNode.removeChild(row);

                    // Check if table is now empty, add "No groups" message
                    const tbody = document.getElementById('expense-groups-tbody');
                    if (tbody && tbody.children.length === 0) {
                        const emptyRow = document.createElement('tr');
                        const emptyCell = document.createElement('td');
                        emptyCell.setAttribute('colspan', '4');
                        emptyCell.className = 'py-4 px-4 text-center text-gray-500';
                        emptyCell.textContent = 'window.DASHBOARD_CONFIG.i18n.noExpenseGroups';
                        emptyRow.appendChild(emptyCell);
                        tbody.appendChild(emptyRow);
                    }

                    // Update balance sheet
                    if (typeof updateBalanceSheet === 'function') {
                        updateBalanceSheet();
                    }

                    // Update pie chart
                    if (typeof updatePieChart === 'function') {
                        updatePieChart();
                    }

                    console.log('[Dashboard RT] FlowGroup removed successfully');
                }
            }, 300);
        },

        /**
         * Reorder FlowGroups in the table
         */
        reorderFlowGroups: function(groupsData) {
            console.log('[Dashboard RT] Reordering FlowGroups:', groupsData);

            const tbody = document.getElementById('expense-groups-tbody');
            if (!tbody) {
                console.warn('[Dashboard RT] Expense groups tbody not found');
                return;
            }

            // Create a map of group_id -> order
            const orderMap = {};
            groupsData.forEach(function(group) {
                orderMap[group.id] = group.order;
            });

            // Update data-order attributes
            const rows = Array.from(tbody.querySelectorAll('tr[data-group-id]'));
            rows.forEach(function(row) {
                const groupId = row.dataset.groupId;
                if (orderMap[groupId]) {
                    row.dataset.order = orderMap[groupId];
                }
            });

            // Sort rows by order
            rows.sort(function(a, b) {
                const orderA = parseInt(a.dataset.order) || 0;
                const orderB = parseInt(b.dataset.order) || 0;
                return orderA - orderB;
            });

            // Re-append rows in new order
            rows.forEach(function(row) {
                tbody.appendChild(row);
            });

            console.log('[Dashboard RT] FlowGroups reordered successfully');
        }
    };

    console.log('[Dashboard RT] Real-time updates initialized');
})();
