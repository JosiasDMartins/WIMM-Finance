/**
 * FlowGroup_realtime.js - Real-time Updates for FlowGroup Page
 * PHASE 3 CSP Compliance: All inline real-time scripts moved to external file
 * Version: 20251230-003
 * Handles WebSocket broadcasts to update the page when other users make changes
 */

(function() {
    'use strict';

    // FlowGroup Real-time Updates Namespace
    window.FlowGroupRealtime = {
        /**
         * Add new transaction to the list
         */
        addTransaction: function(transactionData) {
            console.log('[FlowGroup RT] Adding new transaction:', transactionData);

            // Check if transaction belongs to this FlowGroup
            const currentFlowGroupId = document.getElementById('flow-group-form')?.getAttribute('data-flow-group-id');
            if (!currentFlowGroupId || transactionData.flow_group.id != currentFlowGroupId) {
                console.log('[FlowGroup RT] Transaction not for this FlowGroup, skipping');
                return;
            }

            const tbody = document.getElementById('expense-items-body');
            if (!tbody) {
                console.warn('[FlowGroup RT] Items tbody not found');
                return;
            }

            // Check if transaction already exists (avoid duplicates)
            const existingRow = document.getElementById(`item-${transactionData.id}`);
            if (existingRow) {
                console.log('[FlowGroup RT] Transaction already exists, updating instead');
                this.updateTransaction(transactionData);
                return;
            }

            // Check if it's the new-item-template row waiting to be converted
            const templateRow = document.getElementById('new-item-template');
            if (templateRow && !templateRow.classList.contains('hidden')) {
                console.log('[FlowGroup RT] New item template is visible, likely own action - skipping reload');
                // The template will be hidden by saveItem() after successful save
                // Just update the display when the row is properly created
                setTimeout(() => {
                    const newRow = document.getElementById(`item-${transactionData.id}`);
                    if (newRow) {
                        this.updateTransaction(transactionData);
                    }
                }, 500);
                return;
            }

            // Reload the page to show new transaction added by another user
            console.log('[FlowGroup RT] New transaction added by another user, reloading...');
            location.reload();
        },

        /**
         * Update existing transaction
         */
        updateTransaction: function(transactionData) {
            console.log('[FlowGroup RT] Updating transaction:', transactionData);

            // Check if transaction belongs to this FlowGroup
            const currentFlowGroupId = document.getElementById('flow-group-form')?.getAttribute('data-flow-group-id');
            if (!currentFlowGroupId || transactionData.flow_group.id != currentFlowGroupId) {
                return;
            }

            const row = document.getElementById(`item-${transactionData.id}`);
            if (!row) {
                console.warn('[FlowGroup RT] Transaction row not found:', `item-${transactionData.id}`);
                return;
            }

            console.log('[FlowGroup RT] Updating row elements...');
            try {
                // Update description display
                const descDisplay = row.querySelector('.cell-description-display');
                if (descDisplay) {
                    descDisplay.textContent = transactionData.description;
                }

                // Update amount display (preserve mobile action buttons!)
                const amountDisplay = row.querySelector('.cell-budget-display');
                if (amountDisplay && transactionData.currency_symbol) {
                    const formattedAmount = window.RealtimeUI.utils.formatCurrency(transactionData.amount);
                    // Don't use textContent as it removes mobile action buttons!
                    // Instead, find/create text node or update only the text part
                    const mobileActions = amountDisplay.querySelector('.mobile-actions-btns');

                    if (mobileActions) {
                        // Mobile buttons exist - preserve them
                        // Remove all text nodes and replace with new amount
                        Array.from(amountDisplay.childNodes).forEach(node => {
                            if (node.nodeType === Node.TEXT_NODE) {
                                node.remove();
                            }
                        });
                        // Insert formatted amount as first child (before mobile-actions-btns)
                        amountDisplay.insertBefore(document.createTextNode(formattedAmount + '\n                        '), amountDisplay.firstChild);
                    } else {
                        // No mobile buttons - safe to use textContent
                        amountDisplay.textContent = formattedAmount;
                    }
                }

                // Update date display (fix timezone issue - add T00:00:00 to force local time)
                if (transactionData.date) {
                    const dateFull = row.querySelector('.date-full');
                    const dateShort = row.querySelector('.date-short');
                    if (dateFull && dateShort) {
                        // Add T00:00:00 to prevent timezone conversion (prevents -1 day bug)
                        const dateObj = new Date(transactionData.date + 'T00:00:00');
                        const year = dateObj.getFullYear();
                        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
                        const day = String(dateObj.getDate()).padStart(2, '0');
                        dateFull.textContent = `${year}-${month}-${day}`;
                        dateShort.textContent = `${day}/${month}`;
                    }
                }

                // Update member display
                if (transactionData.member !== undefined) {
                    const memberDisplay = row.querySelector('.cell-member-display');
                    if (memberDisplay) {
                        memberDisplay.textContent = transactionData.member || '-';
                        if (transactionData.member_id) {
                            memberDisplay.setAttribute('data-member-id', transactionData.member_id);
                        }
                    }
                }

                // Update data attributes
                row.setAttribute('data-amount', transactionData.amount);
                row.setAttribute('data-realized', transactionData.realized ? 'true' : 'false');
                row.setAttribute('data-fixed', transactionData.is_fixed ? 'true' : 'false');

                // Update realized toggle
                const toggleBtn = row.querySelector('.realized-toggle');
                if (toggleBtn) {
                    const toggleCircle = toggleBtn.querySelector('span');
                    if (transactionData.realized) {
                        toggleBtn.classList.remove('bg-gray-300', 'dark:bg-gray-600');
                        toggleBtn.classList.add('bg-green-500');
                        if (toggleCircle) toggleCircle.classList.add('translate-x-4');
                    } else {
                        toggleBtn.classList.remove('bg-green-500');
                        toggleBtn.classList.add('bg-gray-300', 'dark:bg-gray-600');
                        if (toggleCircle) toggleCircle.classList.remove('translate-x-4');
                    }
                }

                // Update desktop fixed toggle button
                const fixedToggleBtn = row.querySelector('.fixed-toggle-btn');
                if (fixedToggleBtn) {
                    if (transactionData.is_fixed) {
                        fixedToggleBtn.classList.remove('bg-gray-200', 'dark:bg-gray-700', 'text-gray-400', 'dark:text-gray-500', 'hover:bg-blue-200', 'dark:hover:bg-blue-900/30');
                        fixedToggleBtn.classList.add('bg-blue-600', 'text-white', 'hover:bg-blue-700');
                    } else {
                        fixedToggleBtn.classList.remove('bg-blue-600', 'text-white', 'hover:bg-blue-700');
                        fixedToggleBtn.classList.add('bg-gray-200', 'dark:bg-gray-700', 'text-gray-400', 'dark:text-gray-500', 'hover:bg-blue-200', 'dark:hover:bg-blue-900/30');
                    }
                }

                // Update mobile fixed button
                const mobileFixedBtn = row.querySelector('.mobile-fixed-btn');
                if (mobileFixedBtn) {
                    if (transactionData.is_fixed) {
                        mobileFixedBtn.classList.add('active');
                    } else {
                        mobileFixedBtn.classList.remove('active');
                    }
                }

                // Update row classes for fixed status (mobile border)
                if (transactionData.is_fixed) {
                    row.classList.add('row-fixed');
                } else {
                    row.classList.remove('row-fixed');
                }

                // Update row classes for realized status
                if (transactionData.realized) {
                    row.classList.remove('row-not-realized');
                    row.classList.add('row-realized');
                } else {
                    row.classList.remove('row-realized');
                    row.classList.add('row-not-realized');
                }

                // Highlight the updated row
                if (window.RealtimeUI && window.RealtimeUI.utils && window.RealtimeUI.utils.highlightElement) {
                    window.RealtimeUI.utils.highlightElement(row, 2000);
                }

                console.log('[FlowGroup RT] Transaction updated successfully:', transactionData.id);
            } catch (error) {
                console.error('[FlowGroup RT] Error updating transaction:', error);
            }
        },

        /**
         * Remove transaction from the list
         */
        removeTransaction: function(transactionId) {
            console.log('[FlowGroup RT] Removing transaction:', transactionId);

            const row = document.getElementById(`item-${transactionId}`);
            if (!row) {
                console.warn('[FlowGroup RT] Transaction row not found');
                return;
            }

            // Fade out animation
            row.style.transition = 'opacity 0.3s ease';
            row.style.opacity = '0';

            setTimeout(() => {
                if (row.parentNode) {
                    row.parentNode.removeChild(row);
                    console.log('[FlowGroup RT] Transaction removed successfully');
                }
            }, 300);
        },

        /**
         * Update FlowGroup details (name, budget, checkboxes, etc.)
         */
        updateFlowGroup: function(flowgroupData) {
            console.log('[FlowGroup RT] Updating FlowGroup:', flowgroupData);

            // Check if this is the current FlowGroup
            const currentFlowGroupId = document.getElementById('flow-group-form')?.getAttribute('data-flow-group-id');
            if (!currentFlowGroupId || flowgroupData.id != currentFlowGroupId) {
                return;
            }

            try {
                // Update name in title
                const titleElement = document.querySelector('h1.text-2xl');
                if (titleElement && flowgroupData.name) {
                    const backArrow = titleElement.querySelector('a');
                    if (backArrow) {
                        const textNode = titleElement.childNodes[titleElement.childNodes.length - 1];
                        if (textNode) {
                            textNode.textContent = ' ' + flowgroupData.name;
                        }
                    }
                }

                // Update name input
                const nameInput = document.getElementById('id_name');
                if (nameInput && flowgroupData.name) {
                    nameInput.value = flowgroupData.name;
                }

                // Update budgeted_amount input
                const budgetInput = document.getElementById('id_budgeted_amount');
                if (budgetInput && flowgroupData.budgeted_amount) {
                    budgetInput.value = flowgroupData.budgeted_amount;
                }

                // Update checkboxes
                const isSharedCheckbox = document.getElementById('id_is_shared');
                if (isSharedCheckbox) {
                    isSharedCheckbox.checked = flowgroupData.is_shared;
                }

                const isKidsGroupCheckbox = document.getElementById('id_is_kids_group');
                if (isKidsGroupCheckbox) {
                    isKidsGroupCheckbox.checked = flowgroupData.is_kids_group;
                }

                const isInvestmentCheckbox = document.getElementById('id_is_investment');
                if (isInvestmentCheckbox) {
                    isInvestmentCheckbox.checked = flowgroupData.is_investment;
                }

                const isCreditCardCheckbox = document.getElementById('id_is_credit_card');
                if (isCreditCardCheckbox) {
                    isCreditCardCheckbox.checked = flowgroupData.is_credit_card;

                    // Show/hide credit card closed button based on checkbox
                    const closedBtnContainer = document.querySelector('[data-action="toggle-creditcard-closed"]')?.closest('.flex, .inline-flex');
                    if (closedBtnContainer) {
                        if (flowgroupData.is_credit_card) {
                            closedBtnContainer.style.display = '';
                        } else {
                            closedBtnContainer.style.display = 'none';
                        }
                    }
                }

                // Update assigned members multi-select
                if (flowgroupData.assigned_members) {
                    const membersSelect = document.getElementById('id_assigned_members');
                    if (membersSelect) {
                        Array.from(membersSelect.options).forEach(option => {
                            option.selected = flowgroupData.assigned_members.includes(parseInt(option.value));
                        });
                    }
                }

                // Update assigned children multi-select
                if (flowgroupData.assigned_children) {
                    const childrenSelect = document.getElementById('id_assigned_children');
                    if (childrenSelect) {
                        Array.from(childrenSelect.options).forEach(option => {
                            option.selected = flowgroupData.assigned_children.includes(parseInt(option.value));
                        });
                    }
                }

                // Update recurring toggle button (desktop and mobile)
                // CRITICAL FIX: Update BOTH buttons (desktop and mobile)
                const recurringBtns = document.querySelectorAll('.recurring-btn');
                recurringBtns.forEach(recurringBtn => {
                    if (flowgroupData.is_recurring) {
                        recurringBtn.classList.remove('bg-blue-600/30', 'text-blue-600', 'dark:text-blue-400', 'hover:bg-blue-600/50');
                        recurringBtn.classList.add('bg-blue-600', 'text-white', 'hover:bg-blue-700');

                        // Update inner circle color
                        const innerCircle = recurringBtn.querySelector('span.flex');
                        if (innerCircle) {
                            innerCircle.classList.remove('bg-blue-700/50');
                            innerCircle.classList.add('bg-blue-800');
                        }
                    } else {
                        recurringBtn.classList.remove('bg-blue-600', 'text-white', 'hover:bg-blue-700');
                        recurringBtn.classList.add('bg-blue-600/30', 'text-blue-600', 'dark:text-blue-400', 'hover:bg-blue-600/50');

                        // Update inner circle color
                        const innerCircle = recurringBtn.querySelector('span.flex');
                        if (innerCircle) {
                            innerCircle.classList.remove('bg-blue-800');
                            innerCircle.classList.add('bg-blue-700/50');
                        }
                    }
                });

                // Update kids realized toggle button
                if (flowgroupData.is_kids_group) {
                    const kidsRealizedBtn = document.querySelector('[data-action="toggle-kids-realized"]');
                    if (kidsRealizedBtn && window.FLOWGROUP_CONFIG) {
                        const icon = kidsRealizedBtn.querySelector('span.material-symbols-outlined');
                        const text = kidsRealizedBtn.querySelector('span:not(.material-symbols-outlined)');
                        if (flowgroupData.realized) {
                            kidsRealizedBtn.classList.remove('bg-gray-200', 'dark:bg-gray-700', 'text-gray-700', 'dark:text-gray-300');
                            kidsRealizedBtn.classList.add('bg-green-500', 'text-white');
                            kidsRealizedBtn.setAttribute('data-current-state', 'true');
                            if (icon) icon.textContent = 'check_circle';
                            if (text) text.textContent = window.FLOWGROUP_CONFIG.i18n.realized || 'Realized';
                        } else {
                            kidsRealizedBtn.classList.remove('bg-green-500', 'text-white');
                            kidsRealizedBtn.classList.add('bg-gray-200', 'dark:bg-gray-700', 'text-gray-700', 'dark:text-gray-300');
                            kidsRealizedBtn.setAttribute('data-current-state', 'false');
                            if (icon) icon.textContent = 'cancel';
                            if (text) text.textContent = window.FLOWGROUP_CONFIG.i18n.notRealized || 'Not Realized';
                        }
                    }
                }

                // Update credit card closed toggle button
                if (flowgroupData.is_credit_card) {
                    const closedBtn = document.querySelector('[data-action="toggle-creditcard-closed"]');
                    if (closedBtn && window.FLOWGROUP_CONFIG) {
                        const icon = closedBtn.querySelector('span.material-symbols-outlined');
                        const text = closedBtn.querySelector('span:not(.material-symbols-outlined)');
                        if (flowgroupData.closed) {
                            closedBtn.classList.remove('bg-gray-200', 'dark:bg-gray-700', 'text-gray-700', 'dark:text-gray-300');
                            closedBtn.classList.add('bg-green-500', 'text-white');
                            closedBtn.setAttribute('data-current-state', 'true');
                            if (icon) icon.textContent = 'check_circle';
                            if (text) text.textContent = window.FLOWGROUP_CONFIG.i18n.billClosed || 'Bill Closed';
                        } else {
                            closedBtn.classList.remove('bg-green-500', 'text-white');
                            closedBtn.classList.add('bg-gray-200', 'dark:bg-gray-700', 'text-gray-700', 'dark:text-gray-300');
                            closedBtn.setAttribute('data-current-state', 'false');
                            if (icon) icon.textContent = 'cancel';
                            if (text) text.textContent = window.FLOWGROUP_CONFIG.i18n.billOpen || 'Bill Open';
                        }
                    }
                }

                // Update totals display in the totals row (both desktop and mobile)
                const estimatedDisplayDesktop = document.getElementById('total-expenses-desktop');
                const estimatedDisplayMobile = document.getElementById('total-expenses-mobile');
                if (flowgroupData.total_estimated) {
                    const formattedEstimated = window.RealtimeUI.utils.formatCurrency(flowgroupData.total_estimated);
                    if (estimatedDisplayDesktop) estimatedDisplayDesktop.textContent = formattedEstimated;
                    if (estimatedDisplayMobile) estimatedDisplayMobile.textContent = formattedEstimated;
                }

                const realizedDisplayDesktop = document.getElementById('total-realized-desktop');
                const realizedDisplayMobile = document.getElementById('total-realized-mobile');
                if (flowgroupData.total_realized) {
                    const formattedRealized = window.RealtimeUI.utils.formatCurrency(flowgroupData.total_realized);
                    if (realizedDisplayDesktop) realizedDisplayDesktop.textContent = formattedRealized;
                    if (realizedDisplayMobile) realizedDisplayMobile.textContent = formattedRealized;
                }

                console.log('[FlowGroup RT] FlowGroup updated successfully');
            } catch (error) {
                console.error('[FlowGroup RT] Error updating FlowGroup:', error);
            }
        },

        /**
         * Handle FlowGroup deletion
         */
        handleFlowGroupDeleted: function(data) {
            console.log('[FlowGroup RT] FlowGroup deleted:', data);

            // Extract FlowGroup data from WebSocket message structure
            const flowgroupData = data.data || data;
            const flowgroupId = flowgroupData.id;
            const flowgroupName = flowgroupData.name || '';

            // Check if this is the current FlowGroup
            const currentFlowGroupId = document.getElementById('flow-group-form')?.getAttribute('data-flow-group-id');
            if (!currentFlowGroupId || flowgroupId != currentFlowGroupId) {
                return;
            }

            // Check if current user deleted it
            const currentUserId = document.body.dataset.userId ? parseInt(document.body.dataset.userId) : null;
            const isOwnAction = data.actor && data.actor.id === currentUserId;

            // Prepare message based on who deleted
            let title, message, iconColor, iconBgColor;

            if (isOwnAction) {
                // Own action - success message
                title = window.FLOWGROUP_CONFIG?.i18n?.flowGroupDeletedSuccess || 'FlowGroup Deleted Successfully';
                message = window.FLOWGROUP_CONFIG?.i18n?.flowGroupDeleted || 'The FlowGroup was successfully deleted.';
                iconColor = "text-green-600 dark:text-green-400";
                iconBgColor = "bg-green-100 dark:bg-green-900/30";
            } else {
                // Another user's action - informational message
                title = window.FLOWGROUP_CONFIG?.i18n?.flowGroupDeletedTitle || 'FlowGroup Deleted';
                const actorName = data.actor ? data.actor.username : (window.FLOWGROUP_CONFIG?.i18n?.anotherUser || 'another user');
                const deletedBy = window.FLOWGROUP_CONFIG?.i18n?.flowGroupDeletedByUser || 'This FlowGroup was deleted by';
                message = `${deletedBy} <strong>${actorName}</strong>.`;
                iconColor = "text-red-600 dark:text-red-400";
                iconBgColor = "bg-red-100 dark:bg-red-900/30";
            }

            // Show modal informing user
            const modalHtml = `
                <div id="flowgroup-deleted-modal" class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
                    <div class="relative mx-auto p-5 border w-96 shadow-lg rounded-md bg-white dark:bg-gray-800">
                        <div class="mt-3 text-center">
                            <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full ${iconBgColor}">
                                <span class="material-symbols-outlined ${iconColor}">${isOwnAction ? 'check_circle' : 'delete'}</span>
                            </div>
                            <h3 class="text-lg leading-6 font-medium text-gray-900 dark:text-white mt-5">
                                ${title}
                            </h3>
                            <div class="mt-2 px-7 py-3">
                                <p class="text-sm text-gray-500 dark:text-gray-400">
                                    ${message}
                                </p>
                                <p class="text-sm font-semibold text-gray-700 dark:text-gray-300 mt-2">${flowgroupName}</p>
                            </div>
                            <div class="items-center px-4 py-3">
                                <button id="flowgroup-deleted-ok-btn"
                                        class="px-4 py-2 bg-primary text-white text-base font-medium rounded-md w-full shadow-sm hover:bg-primary/80 focus:outline-none focus:ring-2 focus:ring-primary">
                                    ${window.FLOWGROUP_CONFIG?.i18n?.ok || 'OK'}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            document.body.insertAdjacentHTML('beforeend', modalHtml);

            // Add click handler to OK button
            const okBtn = document.getElementById('flowgroup-deleted-ok-btn');
            if (okBtn) {
                okBtn.addEventListener('click', function() {
                    window.location.href = window.FLOWGROUP_CONFIG?.urls?.dashboard || '/';
                });
            }
        }
    };

    // Listen for FlowGroup deletion events
    document.addEventListener('realtime:flowgroup:deleted', function(event) {
        if (window.FlowGroupRealtime && window.FlowGroupRealtime.handleFlowGroupDeleted) {
            window.FlowGroupRealtime.handleFlowGroupDeleted(event.detail.data);
        }
    });

    console.log('[FlowGroup RT] Real-time updates initialized');
    console.log('[FlowGroup RT] window.FlowGroupRealtime =', window.FlowGroupRealtime);
    console.log('[FlowGroup RT] window.FlowGroupRealtime.updateTransaction =', window.FlowGroupRealtime.updateTransaction);
})();
