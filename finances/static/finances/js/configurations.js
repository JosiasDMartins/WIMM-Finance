// ============================================
// CONFIGURATIONS.JS - PHASE 3 CSP COMPLIANCE
// ============================================
// All inline scripts from configurations.html moved here
// Handles: period type visibility, backup/restore, form submission with period change confirmation
// Version: 20251231-001 - Using utils.js for common functions

// ============================================
// CONFIGURATION INITIALIZATION
// ============================================

function initConfigurations() {
    const config = document.getElementById('config-config');
    if (!config) {
        console.error('[CONFIG] Configuration div not found');
        return;
    }

    // Store configuration globally
    window.CONFIG_CONFIG = {
        // i18n strings
        i18n: {
            errorSavingConfig: config.dataset.i18nErrorSavingConfig || 'An error occurred while saving configuration. Please try again.',
            creatingBackup: config.dataset.i18nCreatingBackup || 'Creating backup...',
            failedToCreateBackup: config.dataset.i18nFailedToCreateBackup || 'Failed to create backup:',
            noFileSelected: config.dataset.i18nNoFileSelected || 'No file selected',
            pleaseSelectBackupFile: config.dataset.i18nPleaseSelectBackupFile || 'Please select a backup file first',
            noFileSelectedTitle: config.dataset.i18nNoFileSelectedTitle || 'No File Selected',
            confirmDatabaseRestore: config.dataset.i18nConfirmDatabaseRestore || 'Confirm Database Restore',
            warningRestore: config.dataset.i18nWarningRestore || 'Restoring a backup will replace ALL current data in your database. This action cannot be undone.',
            importantBackup: config.dataset.i18nImportantBackup || 'It is strongly recommended to create a backup of your current database before proceeding.',
            continueRestore: config.dataset.i18nContinueRestore || 'Do you want to continue with the restore operation?',
            restoring: config.dataset.i18nRestoring || 'Restoring...',
            confirmMigration: config.dataset.i18nConfirmMigration || 'Confirm Migration',
            followingWillHappen: config.dataset.i18nFollowingWillHappen || 'The following will happen:',
            currentPgBackedUp: config.dataset.i18nCurrentPgBackedUp || 'Current PostgreSQL database will be backed up',
            allPgDataDropped: config.dataset.i18nAllPgDataDropped || 'All current PostgreSQL data will be dropped',
            sqliteMigrated: config.dataset.i18nSqliteMigrated || 'SQLite data will be migrated to PostgreSQL',
            proceedMigration: config.dataset.i18nProceedMigration || 'Do you want to proceed with the migration?',
            migrating: config.dataset.i18nMigrating || 'Migrating...',
            migrationSuccessful: config.dataset.i18nMigrationSuccessful || 'Migration Successful',
            dbMigratedSuccessfully: config.dataset.i18nDbMigratedSuccessfully || 'Database migrated successfully from SQLite to PostgreSQL! Redirecting to login page...',
            migrationFailed: config.dataset.i18nMigrationFailed || 'Migration Failed',
            failedToMigrate: config.dataset.i18nFailedToMigrate || 'Failed to migrate backup:',
            details: config.dataset.i18nDetails || 'Details:',
            restoreSuccessful: config.dataset.i18nRestoreSuccessful || 'Restore Successful',
            dbRestoredSuccessfully: config.dataset.i18nDbRestoredSuccessfully || 'Database restored successfully! Redirecting to login page...',
            restoreFailed: config.dataset.i18nRestoreFailed || 'Restore Failed',
            failedToRestore: config.dataset.i18nFailedToRestore || 'Failed to restore backup:',
            restoreError: config.dataset.i18nRestoreError || 'Restore Error'
        }
    };

    // Initialize all functionality
    initPeriodTypeVisibility();
    initPeriodChangeConfirmation();
    initBackupFunctionality();
    initRestoreFunctionality();

    console.log('[CONFIG] Configurations initialized');
}

// ============================================
// PERIOD TYPE FIELD VISIBILITY
// ============================================

function initPeriodTypeVisibility() {
    const periodTypeRadios = document.querySelectorAll('input[name="period_type"]');
    const startingDayField = document.getElementById('starting-day-field');
    const baseDateField = document.getElementById('base-date-field');

    function updateFieldVisibility() {
        const selectedPeriodType = document.querySelector('input[name="period_type"]:checked')?.value;

        if (selectedPeriodType === 'M') {
            startingDayField.style.display = 'block';
            baseDateField.style.display = 'none';
        } else {
            startingDayField.style.display = 'none';
            baseDateField.style.display = 'block';
        }
    }

    periodTypeRadios.forEach(radio => {
        radio.addEventListener('change', updateFieldVisibility);
    });

    updateFieldVisibility();
}

// ============================================
// PERIOD CHANGE CONFIRMATION LOGIC
// ============================================

function initPeriodChangeConfirmation() {
    const configForm = document.getElementById('configuration-form');
    const confirmInput = document.getElementById('confirm-period-change-input');
    const modalConfirmBtn = document.getElementById('modal-confirm-btn');

    if (!configForm) {
        console.warn('[CONFIG] Configuration form not found');
        return;
    }

    configForm.addEventListener('submit', async function(e) {
        // If already confirmed, let it proceed normally
        if (confirmInput && confirmInput.value === 'true') {
            console.log('[CONFIG FORM] Submitting with confirmation');
            return true;
        }

        // Intercept submit to check if period change confirmation is needed
        e.preventDefault();
        console.log('[CONFIG FORM] Form submit intercepted - checking for period changes');

        const formData = new FormData(configForm);

        try {
            const response = await fetch(configForm.action || window.location.href, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            // Check if response is JSON (modal data) or HTML (normal response)
            const contentType = response.headers.get('content-type');

            if (contentType && contentType.includes('application/json')) {
                // Server returned JSON - this means we need to show confirmation modal
                const data = await response.json();

                if (data.requires_confirmation) {
                    console.log('[CONFIG FORM] Period change requires confirmation - showing modal');
                    console.log('[CONFIG FORM] Modal data:', data);

                    // Show the modal with impact data
                    showPeriodChangeModal(data);

                    // Set up confirm button handler
                    if (modalConfirmBtn) {
                        modalConfirmBtn.onclick = function() {
                            console.log('[CONFIG FORM] User confirmed period change');

                            // Set confirmation flag
                            if (confirmInput) {
                                confirmInput.value = 'true';
                            }

                            // Close modal
                            closePeriodChangeModal();

                            // Submit form normally
                            configForm.submit();
                        };
                    }
                }
            } else {
                // Server returned HTML - no confirmation needed, reload page
                console.log('[CONFIG FORM] No confirmation needed - reloading page');
                window.location.reload();
            }
        } catch (error) {
            console.error('[CONFIG FORM] Error submitting form:', error);
            alert(window.CONFIG_CONFIG.i18n.errorSavingConfig);
        }
    });
}

// ============================================
// BACKUP FUNCTIONALITY
// ============================================

function initBackupFunctionality() {
    const backupBtn = document.getElementById('btn-backup-db');
    if (!backupBtn) {
        console.error('Backup button not found! Expected ID: btn-backup-db');
        return;
    }

    backupBtn.addEventListener('click', async function() {
        console.log('Backup button clicked');
        const btn = this;
        const originalText = btn.innerHTML;

        btn.disabled = true;
        btn.innerHTML = `<span class="material-symbols-outlined animate-spin">progress_activity</span> ${window.CONFIG_CONFIG.i18n.creatingBackup}`;

        try {
            console.log('Sending backup request to /create-backup/');
            const response = await fetch('/create-backup/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                }
            });

            console.log('Backup response status:', response.status);
            const data = await response.json();
            console.log('Backup response data:', data);

            if (data.success) {
                console.log('Redirecting to download:', data.filename);
                window.location.href = `/download-backup/${data.filename}/`;
            } else {
                console.error('Backup failed:', data.error);
                alert(window.CONFIG_CONFIG.i18n.failedToCreateBackup + " " + data.error);
            }
        } catch (error) {
            console.error('Error creating backup:', error);
            alert(window.CONFIG_CONFIG.i18n.failedToCreateBackup + " " + error.message);
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    });
}

// ============================================
// RESTORE FUNCTIONALITY
// ============================================

function initRestoreFunctionality() {
    const restoreFileInput = document.getElementById('restore-file-input');
    const restoreFileName = document.getElementById('restore-file-name');
    const btnRestore = document.getElementById('btn-restore-db');

    if (!restoreFileInput || !restoreFileName || !btnRestore) {
        console.warn('[CONFIG] Restore elements not found');
        return;
    }

    restoreFileInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            restoreFileName.textContent = file.name;
            btnRestore.disabled = false;
        } else {
            restoreFileName.textContent = window.CONFIG_CONFIG.i18n.noFileSelected;
            btnRestore.disabled = true;
        }
    });

    btnRestore.addEventListener('click', async function() {
        const file = restoreFileInput.files[0];
        if (!file) {
            GenericModal.alert(
                window.CONFIG_CONFIG.i18n.pleaseSelectBackupFile,
                window.CONFIG_CONFIG.i18n.noFileSelectedTitle
            );
            return;
        }

        // STEP 1: Show initial warning about data loss and recommend backup
        const backupWarningMessage =
            `<p><span class="font-bold text-orange-600 dark:text-orange-400">⚠️ WARNING:</span> ${window.CONFIG_CONFIG.i18n.warningRestore}</p>` +
            `<p class="mt-4"><span class="font-bold text-orange-600 dark:text-orange-400">IMPORTANT:</span> ${window.CONFIG_CONFIG.i18n.importantBackup}</p>` +
            `<p class="mt-4">${window.CONFIG_CONFIG.i18n.continueRestore}</p>`;

        const backupWarning = await GenericModal.confirm(
            backupWarningMessage,
            window.CONFIG_CONFIG.i18n.confirmDatabaseRestore
        );

        if (!backupWarning) {
            return;
        }

        const btn = this;
        const originalText = btn.innerHTML;

        btn.disabled = true;
        btn.innerHTML = `<span class="material-symbols-outlined animate-spin">progress_activity</span> ${window.CONFIG_CONFIG.i18n.restoring}`;

        try {
            // STEP 2: First attempt - check if migration is needed
            const formData = new FormData();
            formData.append('backup_file', file);

            const response = await fetch('/restore-backup/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: formData
            });

            const data = await response.json();

            // STEP 3: Handle migration confirmation if needed
            if (data.needs_migration_confirmation) {
                // SQLite → PostgreSQL migration needed
                btn.disabled = false;
                btn.innerHTML = originalText;

                const migrationMessage =
                    `<p><span class="font-bold text-orange-600 dark:text-orange-400">⚠️ WARNING:</span> ${data.message}</p>` +
                    `<p class="mt-4 font-semibold">${window.CONFIG_CONFIG.i18n.followingWillHappen}</p>` +
                    `<ul class="mt-2 ml-6 space-y-1 list-disc">` +
                        `<li>${window.CONFIG_CONFIG.i18n.currentPgBackedUp}</li>` +
                        `<li>${window.CONFIG_CONFIG.i18n.allPgDataDropped}</li>` +
                        `<li>${window.CONFIG_CONFIG.i18n.sqliteMigrated}</li>` +
                    `</ul>` +
                    `<p class="mt-4">${window.CONFIG_CONFIG.i18n.proceedMigration}</p>`;

                const migrationConfirmed = await GenericModal.confirm(
                    migrationMessage,
                    window.CONFIG_CONFIG.i18n.confirmMigration
                );

                if (!migrationConfirmed) {
                    return;
                }

                // Retry with migration confirmation
                btn.disabled = true;
                btn.innerHTML = `<span class="material-symbols-outlined animate-spin">progress_activity</span> ${window.CONFIG_CONFIG.i18n.migrating}`;

                const formData2 = new FormData();
                formData2.append('backup_file', file);
                formData2.append('confirm_migration', 'true');

                const response2 = await fetch('/restore-backup/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: formData2
                });

                const data2 = await response2.json();

                if (data2.success) {
                    // Migration successful
                    const preview = document.getElementById('restore-preview');
                    const familyName = document.getElementById('restore-family-name');
                    const usersList = document.getElementById('restore-users-list');

                    if (preview && familyName && usersList) {
                        familyName.textContent = data2.family.name;
                        usersList.innerHTML = '';
                        data2.users.forEach(user => {
                            const li = document.createElement('li');
                            li.textContent = `${user.username} (${user.role})`;
                            usersList.appendChild(li);
                        });

                        preview.classList.remove('hidden');
                    }

                    // Show success modal and redirect to login
                    await GenericModal.alert(
                        window.CONFIG_CONFIG.i18n.dbMigratedSuccessfully,
                        window.CONFIG_CONFIG.i18n.migrationSuccessful
                    );

                    // Redirect to login page
                    window.location.href = '/login/';
                } else {
                    // Show detailed error with details if available
                    let errorMsg = window.CONFIG_CONFIG.i18n.failedToMigrate + " " + data2.error;
                    if (data2.details) {
                        errorMsg += "\n\n" + window.CONFIG_CONFIG.i18n.details + "\n" + data2.details;
                    }
                    GenericModal.alert(errorMsg, window.CONFIG_CONFIG.i18n.migrationFailed);
                }

                return;
            }

            // STEP 4: Handle normal restore (no migration needed)
            if (data.success) {
                const preview = document.getElementById('restore-preview');
                const familyName = document.getElementById('restore-family-name');
                const usersList = document.getElementById('restore-users-list');

                if (preview && familyName && usersList) {
                    familyName.textContent = data.family.name;
                    usersList.innerHTML = '';
                    data.users.forEach(user => {
                        const li = document.createElement('li');
                        li.textContent = `${user.username} (${user.role})`;
                        usersList.appendChild(li);
                    });

                    preview.classList.remove('hidden');
                }

                // Show success modal and redirect to login
                await GenericModal.alert(
                    window.CONFIG_CONFIG.i18n.dbRestoredSuccessfully,
                    window.CONFIG_CONFIG.i18n.restoreSuccessful
                );

                // Redirect to login page
                window.location.href = '/login/';
            } else {
                // Show detailed error message
                let errorMessage = data.error;
                if (data.details) {
                    errorMessage += '\n\n' + window.CONFIG_CONFIG.i18n.details + ' ' + data.details;
                }
                GenericModal.alert(errorMessage, window.CONFIG_CONFIG.i18n.restoreFailed);
            }
        } catch (error) {
            console.error('Error restoring backup:', error);
            GenericModal.alert(
                window.CONFIG_CONFIG.i18n.failedToRestore + " " + error.message,
                window.CONFIG_CONFIG.i18n.restoreError
            );
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
            restoreFileInput.value = '';
            restoreFileName.textContent = window.CONFIG_CONFIG.i18n.noFileSelected;
            btn.disabled = true;
        }
    });
}

// ============================================
// HELPER FUNCTIONS
// ============================================

// getCookie - using utils.js

// ============================================
// REAL-TIME SYNCHRONIZATION
// ============================================

// Configuration Real-time Updates
window.ConfigurationRealtime = {
    updateConfiguration: function(configData) {
        console.log('[ConfigurationRT] Updating configuration:', configData);

        // Update Base Currency
        const currencySelect = document.getElementById('id_base_currency');
        if (currencySelect && configData.base_currency) {
            currencySelect.value = configData.base_currency;
            console.log('[ConfigurationRT] Updated base_currency to:', configData.base_currency);
        }

        // Update Period Type
        if (configData.period_type) {
            const periodTypeRadio = document.querySelector(`input[name="period_type"][value="${configData.period_type}"]`);
            if (periodTypeRadio) {
                periodTypeRadio.checked = true;
                console.log('[ConfigurationRT] Updated period_type to:', configData.period_type);

                // Toggle field visibility based on period type
                const startingDayField = document.getElementById('starting-day-field');
                const baseDateField = document.getElementById('base-date-field');

                if (configData.period_type === 'M') {
                    // Monthly - show starting day, hide base date
                    if (startingDayField) startingDayField.style.display = 'block';
                    if (baseDateField) baseDateField.style.display = 'none';
                } else {
                    // Bi-weekly or Weekly - hide starting day, show base date
                    if (startingDayField) startingDayField.style.display = 'none';
                    if (baseDateField) baseDateField.style.display = 'block';
                }
            }
        }

        // Update Starting Day
        const startingDayInput = document.getElementById('id_starting_day');
        if (startingDayInput && configData.starting_day) {
            startingDayInput.value = configData.starting_day;
            console.log('[ConfigurationRT] Updated starting_day to:', configData.starting_day);
        }

        // Update Base Date
        const baseDateInput = document.getElementById('id_base_date');
        if (baseDateInput && configData.base_date) {
            baseDateInput.value = configData.base_date;
            console.log('[ConfigurationRT] Updated base_date to:', configData.base_date);
        }

        // Update Bank Reconciliation Tolerance
        const toleranceInput = document.getElementById('id_bank_reconciliation_tolerance');
        if (toleranceInput && configData.bank_reconciliation_tolerance) {
            toleranceInput.value = configData.bank_reconciliation_tolerance;
            console.log('[ConfigurationRT] Updated bank_reconciliation_tolerance to:', configData.bank_reconciliation_tolerance);
        }
    }
};

// ============================================
// MEMBERS REAL-TIME UPDATES
// ============================================

window.MembersRealtime = {
    addMember: function(memberData) {
        console.log('[MembersRT] Adding member:', memberData);

        const tbody = document.querySelector('table tbody');
        if (!tbody) {
            console.warn('[MembersRT] Members table tbody not found');
            return;
        }

        // Check if member already exists in table (prevent duplicates)
        const existingRow = tbody.querySelector(`tr[data-member-id="${memberData.id}"]`);
        if (existingRow) {
            console.log('[MembersRT] Member already exists in table, skipping duplicate add');
            return;
        }

        // Remove empty message if exists
        const emptyRow = tbody.querySelector('td[colspan="4"]');
        if (emptyRow) {
            emptyRow.parentElement.remove();
        }

        // Create new row
        const newRow = document.createElement('tr');
        newRow.className = 'hover:bg-slate-50 dark:hover:bg-gray-700/50';
        newRow.setAttribute('data-member-id', memberData.id);

        // Get i18n strings from data attributes
        const config = document.getElementById('config-config');
        const viewOnlyText = config ? (config.dataset.i18nViewOnly || 'View only') : 'View only';

        newRow.innerHTML = `
            <td class="px-6 py-4 font-medium text-[#0d171b] dark:text-white">${this.escapeHtml(memberData.username)}</td>
            <td class="px-6 py-4 text-sm text-gray-500">${this.escapeHtml(memberData.email || '-')}</td>
            <td class="px-6 py-4 text-sm text-gray-500">
                <span class="px-2 py-1 text-sm font-medium rounded-full bg-primary/20 text-primary">${this.escapeHtml(memberData.role_display)}</span>
            </td>
            <td class="px-6 py-4 text-center whitespace-nowrap">
                <div class="flex justify-center gap-2">
                    <span class="text-xs text-gray-400 dark:text-gray-500">${viewOnlyText}</span>
                </div>
            </td>
        `;

        tbody.appendChild(newRow);

        // Highlight new row
        if (window.RealtimeUI && window.RealtimeUI.utils && window.RealtimeUI.utils.highlightElement) {
            window.RealtimeUI.utils.highlightElement(newRow, 2000);
        }
    },

    updateMember: function(memberData) {
        console.log('[MembersRT] Updating member:', memberData);

        const row = document.querySelector(`tr[data-member-id="${memberData.id}"]`);
        if (!row) {
            console.warn('[MembersRT] Member row not found for ID:', memberData.id);
            return;
        }

        // Update username
        const usernameCell = row.querySelector('td:nth-child(1)');
        if (usernameCell) {
            usernameCell.textContent = memberData.username;
        }

        // Update email
        const emailCell = row.querySelector('td:nth-child(2)');
        if (emailCell) {
            emailCell.textContent = memberData.email || '-';
        }

        // Update role
        const roleCell = row.querySelector('td:nth-child(3) span');
        if (roleCell) {
            roleCell.textContent = memberData.role_display;
        }

        // Highlight updated row
        if (window.RealtimeUI && window.RealtimeUI.utils && window.RealtimeUI.utils.highlightElement) {
            window.RealtimeUI.utils.highlightElement(row, 2000);
        }
    },

    removeMember: function(memberData) {
        console.log('[MembersRT] Removing member:', memberData);

        const row = document.querySelector(`tr[data-member-id="${memberData.id}"]`);
        if (!row) {
            console.warn('[MembersRT] Member row not found for ID:', memberData.id);
            return;
        }

        // Add fade-out animation
        row.style.transition = 'opacity 0.3s';
        row.style.opacity = '0';

        setTimeout(() => {
            row.remove();

            // Check if table is empty and add empty message
            const tbody = document.querySelector('table tbody');
            if (tbody && tbody.children.length === 0) {
                const config = document.getElementById('config-config');
                const noMembersText = config ? (config.dataset.i18nNoMembers || 'No members found in the family.') : 'No members found in the family.';

                const emptyRow = document.createElement('tr');
                emptyRow.innerHTML = `
                    <td colspan="4" class="px-6 py-4 text-sm text-gray-500 text-center">${noMembersText}</td>
                `;
                tbody.appendChild(emptyRow);
            }
        }, 300);
    },

    escapeHtml: function(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// ============================================
// REAL-TIME EVENT LISTENERS
// ============================================

function initRealtimeListeners() {
    // Listen for configuration events
    document.addEventListener('realtime:configuration:updated', function(event) {
        if (window.ConfigurationRealtime && window.ConfigurationRealtime.updateConfiguration) {
            window.ConfigurationRealtime.updateConfiguration(event.detail.data);
        }
    });

    // Listen for member events
    document.addEventListener('realtime:member:added', function(event) {
        if (window.MembersRealtime && window.MembersRealtime.addMember) {
            window.MembersRealtime.addMember(event.detail.data);
        }
    });

    document.addEventListener('realtime:member:updated', function(event) {
        if (window.MembersRealtime && window.MembersRealtime.updateMember) {
            window.MembersRealtime.updateMember(event.detail.data);
        }
    });

    document.addEventListener('realtime:member:removed', function(event) {
        // Check if current user is the actor (who performed the action)
        // If yes, skip the real-time update as the page will redirect
        const config = document.getElementById('config-config');
        const currentUsername = config ? config.dataset.currentUsername : '';
        const actorUsername = event.detail.actor?.username;

        if (actorUsername && actorUsername === currentUsername) {
            console.log('[MembersRT] Current user is the actor, skipping real-time removal (page will redirect)');
            return;
        }

        if (window.MembersRealtime && window.MembersRealtime.removeMember) {
            window.MembersRealtime.removeMember(event.detail.data);
        }
    });

    console.log('[ConfigurationRealtime] Loaded successfully');
    console.log('[MembersRealtime] Loaded successfully');
}

// ============================================
// ADD MEMBER FORM - PREVENT PAGE RELOAD
// ============================================

function initAddMemberForm() {
    const addMemberForm = document.getElementById('add-member-form');
    if (!addMemberForm) {
        console.warn('[CONFIG] Add member form not found');
        return;
    }

    addMemberForm.addEventListener('submit', function(e) {
        e.preventDefault();

        const formData = new FormData(addMemberForm);
        const submitBtn = addMemberForm.querySelector('button[type="submit"]');

        const config = document.getElementById('config-config');
        const addingText = config ? (config.dataset.i18nAdding || 'Adding...') : 'Adding...';
        const addText = config ? (config.dataset.i18nAdd || 'Add') : 'Add';
        const errorAddingMember = config ? (config.dataset.i18nErrorAddingMember || 'Error adding member. Please try again.') : 'Error adding member. Please try again.';

        // Disable button during submission
        submitBtn.disabled = true;
        submitBtn.innerHTML = `<span class="material-symbols-outlined mr-1 animate-spin">progress_activity</span>${addingText}`;

        fetch(addMemberForm.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => {
            if (response.redirected) {
                // If redirected, means there was an error (redirect to same page with errors)
                // Reload to show errors
                window.location.href = response.url;
            } else {
                // Success - member was added
                // Reset form
                addMemberForm.reset();

                // Re-enable button
                submitBtn.disabled = false;
                submitBtn.innerHTML = `<span class="material-symbols-outlined mr-1">add</span>${addText}`;

                // The WebSocket will add the new row automatically
                console.log('[AddMember] Member added successfully, waiting for WebSocket update');
            }
        })
        .catch(error => {
            console.error('[AddMember] Error:', error);
            submitBtn.disabled = false;
            submitBtn.innerHTML = `<span class="material-symbols-outlined mr-1">add</span>${addText}`;
            alert(errorAddingMember);
        });
    });
}

// ============================================
// PHASE 4: TAB AND MODAL MANAGEMENT
// ============================================

class TabManager {
    constructor() {
        this.activeTab = this.getInitialTab();
        this.init();
    }

    getInitialTab() {
        // Get tab from URL query parameter or default to 'configuration'
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('tab') || 'configuration';
    }

    init() {
        // Setup tab button listeners
        document.querySelectorAll('[data-tab]').forEach(btn => {
            btn.addEventListener('click', () => this.switchTab(btn.dataset.tab));
        });

        // Show initial tab
        this.switchTab(this.activeTab);
    }

    switchTab(tabName) {
        this.activeTab = tabName;

        // Update button states
        document.querySelectorAll('[data-tab]').forEach(btn => {
            if (btn.dataset.tab === tabName) {
                btn.classList.add('border-primary', 'text-primary');
                btn.classList.remove('border-transparent', 'text-gray-500', 'dark:text-gray-400');
            } else {
                btn.classList.remove('border-primary', 'text-primary');
                btn.classList.add('border-transparent', 'text-gray-500', 'dark:text-gray-400');
            }
        });

        // Show/hide tab content
        document.querySelectorAll('[data-tab-content]').forEach(content => {
            if (content.dataset.tabContent === tabName) {
                content.classList.remove('hidden');
            } else {
                content.classList.add('hidden');
            }
        });
    }
}

class MemberModals {
    constructor() {
        this.init();
    }

    init() {
        // Edit member buttons
        document.querySelectorAll('[data-action="edit-member"]').forEach(btn => {
            btn.addEventListener('click', () => {
                this.showEditModal({
                    id: btn.dataset.memberId,
                    username: btn.dataset.memberUsername,
                    email: btn.dataset.memberEmail,
                    role: btn.dataset.memberRole
                });
            });
        });

        // Change password buttons
        document.querySelectorAll('[data-action="change-password"]').forEach(btn => {
            btn.addEventListener('click', () => {
                this.showPasswordModal(btn.dataset.memberId);
            });
        });

        // Delete member buttons
        document.querySelectorAll('[data-action="delete-member"]').forEach(btn => {
            btn.addEventListener('click', () => {
                this.showDeleteModal({
                    id: btn.dataset.memberId,
                    username: btn.dataset.memberUsername
                });
            });
        });

        // Close modal buttons
        document.querySelectorAll('[data-action="close-modal"]').forEach(btn => {
            btn.addEventListener('click', () => {
                this.closeModal(btn.dataset.modalName);
            });
        });

        // Form submissions
        this.setupFormSubmissions();
    }

    setupFormSubmissions() {
        const editForm = document.getElementById('edit-member-form');
        const passwordForm = document.getElementById('password-form');
        const deleteForm = document.getElementById('delete-member-form');

        if (editForm) {
            editForm.addEventListener('submit', (e) => {
                const memberId = document.getElementById('edit-member-id').value;
                const periodParam = new URLSearchParams(window.location.search).get('period');
                const url = `/members/edit/${memberId}/${periodParam ? '?period=' + periodParam : ''}`;
                editForm.action = url;
            });
        }

        if (passwordForm) {
            passwordForm.addEventListener('submit', (e) => {
                const memberId = document.getElementById('password-member-id').value;
                const periodParam = new URLSearchParams(window.location.search).get('period');
                const url = `/members/edit/${memberId}/${periodParam ? '?period=' + periodParam : ''}`;
                passwordForm.action = url;
            });
        }

        if (deleteForm) {
            deleteForm.addEventListener('submit', (e) => {
                const memberId = document.getElementById('delete-member-id').value;
                const periodParam = new URLSearchParams(window.location.search).get('period');
                const tabParam = 'tab=members';
                const url = `/members/remove/${memberId}/${periodParam ? '?period=' + periodParam + '&' + tabParam : '?' + tabParam}`;
                deleteForm.action = url;
            });
        }
    }

    showEditModal(member) {
        const modal = document.getElementById('edit-member-modal');
        document.getElementById('edit-member-id').value = member.id;
        document.getElementById('edit-member-username').value = member.username;
        document.getElementById('edit-member-email').value = member.email || '';
        document.getElementById('edit-member-role').value = member.role;
        modal.classList.remove('hidden');
    }

    showPasswordModal(memberId) {
        const modal = document.getElementById('password-modal');
        document.getElementById('password-member-id').value = memberId;
        modal.classList.remove('hidden');
    }

    showDeleteModal(member) {
        const modal = document.getElementById('delete-member-modal');
        document.getElementById('delete-member-id').value = member.id;
        document.getElementById('delete-member-username').textContent = member.username;
        modal.classList.remove('hidden');
    }

    closeModal(modalName) {
        const modal = document.getElementById(`${modalName}-modal`);
        if (modal) {
            modal.classList.add('hidden');

            // Clear form fields
            if (modalName === 'edit-member') {
                document.getElementById('edit-member-form').reset();
            } else if (modalName === 'password') {
                document.getElementById('password-form').reset();
            }
        }
    }
}

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    initConfigurations();
    initRealtimeListeners();
    initAddMemberForm();

    window.tabManager = new TabManager();
    window.memberModals = new MemberModals();

    console.log('[Phase4-TabManager] Initialized');
    console.log('[Phase4-MemberModals] Initialized');
});
