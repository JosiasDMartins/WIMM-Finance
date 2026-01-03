// ============================================
// SETUP.JS - PHASE 3 CSP COMPLIANCE
// ============================================
// All inline scripts from setup.html moved here
// Handles: Service worker unregistration, period type visibility, backup restore
// Version: 20251231-001
// Depends on: base.js (GenericModal), utils.js (getCookie)

// ============================================
// SERVICE WORKER UNREGISTRATION
// ============================================

// Flag to track if service workers are fully unregistered
window.serviceWorkersUnregistered = false;

if ('serviceWorker' in navigator) {
    navigator.serviceWorker.getRegistrations().then(function(registrations) {
        if (registrations.length === 0) {
            console.log('[SETUP] No service workers to unregister');
            window.serviceWorkersUnregistered = true;
            return;
        }

        let unregisteredCount = 0;
        const totalRegistrations = registrations.length;

        registrations.forEach(function(registration) {
            registration.unregister().then(function(success) {
                if (success) {
                    console.log('[SETUP] Unregistered service worker successfully');
                } else {
                    console.error('[SETUP] Failed to unregister service worker');
                }
                unregisteredCount++;

                // All service workers unregistered
                if (unregisteredCount === totalRegistrations) {
                    console.log('[SETUP] All service workers unregistered');
                    window.serviceWorkersUnregistered = true;
                }
            });
        });
    }).catch(function(error) {
        console.error('[SETUP] Error getting service worker registrations:', error);
        // Even if there's an error, allow the page to function
        window.serviceWorkersUnregistered = true;
    });
} else {
    // Service workers not supported or not available
    window.serviceWorkersUnregistered = true;
}

// ============================================
// SETUP INITIALIZATION
// ============================================

function initSetup() {
    const config = document.getElementById('setup-config');
    if (!config) {
        console.error('[SETUP] Configuration div not found');
        return;
    }

    // Store configuration globally
    window.SETUP_CONFIG = {
        i18n: {
            noFileSelected: config.dataset.i18nNoFileSelected || 'No file selected',
            checkingServiceWorkers: config.dataset.i18nCheckingServiceWorkers || 'Checking service workers...',
            serviceWorkersError: config.dataset.i18nServiceWorkersError || 'Service workers could not be unregistered. Please refresh the page and try again.',
            uploadBackup: config.dataset.i18nUploadBackup || 'Upload Backup',
            restoring: config.dataset.i18nRestoring || 'Restoring...',
            serverError: config.dataset.i18nServerError || 'Server returned non-JSON response. Please check server logs.',
            dbRestoredSuccessfully: config.dataset.i18nDbRestoredSuccessfully || 'Database restored successfully!',
            migrationWarning: config.dataset.i18nMigrationWarning || 'Note: Some migrations encountered warnings. Check console for details.',
            migrationSuccess: config.dataset.i18nMigrationSuccess || 'Database structure updated to latest version.',
            clickOkToLogin: config.dataset.i18nClickOkToLogin || 'Click OK to go to login page.',
            restoreFailed: config.dataset.i18nRestoreFailed || 'Restore failed:',
            unknownError: config.dataset.i18nUnknownError || 'Unknown error',
            errorRestoringDatabase: config.dataset.i18nErrorRestoringDatabase || 'Error restoring database:',
            restoreBackup: config.dataset.i18nRestoreBackup || 'Restore Backup',
            restoreSuccessful: config.dataset.i18nRestoreSuccessful || 'Restore Successful',
            restoreError: config.dataset.i18nRestoreError || 'Restore Error'
        }
    };

    // Initialize all functionality
    initPeriodTypeVisibility();
    initSectionToggle();
    initBackupRestore();

    console.log('[SETUP] Setup initialized');
}

// ============================================
// PERIOD TYPE FIELD VISIBILITY
// ============================================

function initPeriodTypeVisibility() {
    const periodTypeRadios = document.querySelectorAll('input[name="period_type"]');
    const startingDayField = document.getElementById('starting-day-field');
    const baseDateField = document.getElementById('base-date-field');

    if (!periodTypeRadios.length || !startingDayField || !baseDateField) {
        console.warn('[SETUP] Period type elements not found');
        return;
    }

    function updateFieldsVisibility() {
        const selectedType = document.querySelector('input[name="period_type"]:checked');
        if (!selectedType) return;

        const value = selectedType.value;
        const baseDateInput = baseDateField.querySelector('input');

        if (value === 'M') {
            // Monthly - show starting_day, hide base_date
            startingDayField.style.display = 'block';
            baseDateField.style.display = 'none';

            // Remove required from base_date when hidden
            if (baseDateInput) baseDateInput.removeAttribute('required');
        } else {
            // Bi-weekly or Weekly - hide starting_day, show base_date
            startingDayField.style.display = 'none';
            baseDateField.style.display = 'block';

            // Add required to base_date when visible
            if (baseDateInput) baseDateInput.setAttribute('required', 'required');
        }
    }

    // Initial setup
    updateFieldsVisibility();

    // Listen for changes
    periodTypeRadios.forEach(radio => {
        radio.addEventListener('change', updateFieldsVisibility);
    });
}

// ============================================
// SECTION TOGGLE (RESTORE/SETUP)
// ============================================

function initSectionToggle() {
    const btnShowRestore = document.getElementById('btn-show-restore');
    const btnShowSetup = document.getElementById('btn-show-setup');
    const restoreSection = document.getElementById('restore-section');
    const setupSection = document.getElementById('setup-section');
    const btnCancelRestore = document.getElementById('btn-cancel-restore');

    if (!btnShowRestore || !btnShowSetup || !restoreSection || !setupSection) {
        console.warn('[SETUP] Section toggle elements not found');
        return;
    }

    // Toggle to restore section
    btnShowRestore.addEventListener('click', function() {
        restoreSection.classList.remove('hidden');
        setupSection.classList.add('hidden');
        btnShowRestore.classList.add('bg-teal-50');
        btnShowSetup.classList.remove('bg-teal-500', 'text-white');
        btnShowSetup.classList.add('border-2', 'border-teal-500', 'text-teal-600');
    });

    // Toggle to setup section
    btnShowSetup.addEventListener('click', function() {
        setupSection.classList.remove('hidden');
        restoreSection.classList.add('hidden');
        btnShowSetup.classList.remove('border-2', 'border-teal-500', 'text-teal-600');
        btnShowSetup.classList.add('bg-teal-500', 'text-white');
        btnShowRestore.classList.remove('bg-teal-50');
    });

    // Cancel restore
    if (btnCancelRestore) {
        btnCancelRestore.addEventListener('click', function() {
            btnShowSetup.click();
        });
    }
}

// ============================================
// BACKUP RESTORE FUNCTIONALITY
// ============================================

function initBackupRestore() {
    const backupFileInput = document.getElementById('backup-file-input');
    const fileNameDisplay = document.getElementById('file-name');
    const btnUploadBackup = document.getElementById('btn-upload-backup');
    const restoreInfo = document.getElementById('restore-info');

    if (!backupFileInput || !fileNameDisplay || !btnUploadBackup) {
        console.warn('[SETUP] Backup restore elements not found');
        return;
    }

    // Handle file selection
    backupFileInput.addEventListener('change', function(e) {
        if (e.target.files.length > 0) {
            const file = e.target.files[0];
            fileNameDisplay.textContent = file.name;
            btnUploadBackup.disabled = false;
        } else {
            fileNameDisplay.textContent = window.SETUP_CONFIG.i18n.noFileSelected;
            btnUploadBackup.disabled = true;
            if (restoreInfo) restoreInfo.classList.add('hidden');
        }
    });

    // Handle backup upload
    btnUploadBackup.addEventListener('click', async function() {
        const file = backupFileInput.files[0];
        if (!file) return;

        // CRITICAL: Wait for service workers to be unregistered before proceeding
        // Service workers can hold database connections that prevent file operations
        btnUploadBackup.disabled = true;
        btnUploadBackup.innerHTML = `<span class="material-symbols-outlined animate-spin">progress_activity</span> ${window.SETUP_CONFIG.i18n.checkingServiceWorkers}`;

        console.log('[RESTORE] Waiting for service workers to be unregistered...');
        const maxWaitTime = 5000; // 5 seconds
        const startTime = Date.now();

        // Wait for service workers to be unregistered
        while (!window.serviceWorkersUnregistered && (Date.now() - startTime) < maxWaitTime) {
            await new Promise(resolve => setTimeout(resolve, 100));
        }

        if (!window.serviceWorkersUnregistered) {
            console.error('[RESTORE] Service workers still not unregistered after 5 seconds');
            await window.GenericModal.alert(
                window.SETUP_CONFIG.i18n.serviceWorkersError,
                window.SETUP_CONFIG.i18n.restoreError
            );
            btnUploadBackup.disabled = false;
            btnUploadBackup.innerHTML = `<span class="material-symbols-outlined">upload</span> ${window.SETUP_CONFIG.i18n.uploadBackup}`;
            return;
        }

        console.log('[RESTORE] Service workers unregistered, proceeding with restore');

        // Close any existing WebSocket connections before restore
        // This prevents database lock issues during restore
        if (window.updateSocket && window.updateSocket.readyState === WebSocket.OPEN) {
            console.log('[RESTORE] Closing WebSocket before database restore');
            window.updateSocket.close();
        }

        const formData = new FormData();
        formData.append('backup_file', file);

        btnUploadBackup.innerHTML = `<span class="material-symbols-outlined animate-spin">progress_activity</span> ${window.SETUP_CONFIG.i18n.restoring}`;

        try {
            const response = await fetch('/restore-backup/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': window.getCookie('csrftoken')
                },
                body: formData
            });

            // Check if response is JSON
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                const text = await response.text();
                console.error('Non-JSON response:', text);
                throw new Error(window.SETUP_CONFIG.i18n.serverError);
            }

            const data = await response.json();

            if (data.success) {
                // Show backup info
                if (restoreInfo) {
                    restoreInfo.classList.remove('hidden');
                    const familyName = document.getElementById('family-name');
                    if (familyName) familyName.textContent = data.family.name;

                    const usersList = document.getElementById('users-list');
                    if (usersList) {
                        usersList.innerHTML = '';
                        data.users.forEach(user => {
                            const li = document.createElement('li');
                            li.textContent = `${user.username} (${user.role})${user.email ? ' - ' + user.email : ''}`;
                            usersList.appendChild(li);
                        });
                    }
                }

                // Log migration results if available
                if (data.migration_log) {
                    console.log('Migration log:', data.migration_log);
                }

                // Show success and redirect option
                let message = window.SETUP_CONFIG.i18n.dbRestoredSuccessfully;
                if (data.migration_log && data.migration_log.includes('Warning')) {
                    message += '\n\n' + window.SETUP_CONFIG.i18n.migrationWarning;
                } else if (data.migration_log) {
                    message += '\n\n' + window.SETUP_CONFIG.i18n.migrationSuccess;
                }

                message += '\n\n' + window.SETUP_CONFIG.i18n.clickOkToLogin;

                // Use GenericModal for confirmation
                setTimeout(async () => {
                    const confirmed = await window.GenericModal.confirm(
                        message,
                        window.SETUP_CONFIG.i18n.restoreSuccessful
                    );
                    if (confirmed) {
                        window.location.href = '/login/';
                    }
                }, 1000);

            } else {
                const errorMsg = window.SETUP_CONFIG.i18n.restoreFailed + ' ' + (data.error || window.SETUP_CONFIG.i18n.unknownError);
                await window.GenericModal.alert(errorMsg, window.SETUP_CONFIG.i18n.restoreError);
                btnUploadBackup.disabled = false;
                btnUploadBackup.innerHTML = window.SETUP_CONFIG.i18n.restoreBackup;
            }
        } catch (error) {
            console.error('Restore error:', error);
            const errorMsg = window.SETUP_CONFIG.i18n.errorRestoringDatabase + ' ' + error.message;
            await window.GenericModal.alert(errorMsg, window.SETUP_CONFIG.i18n.restoreError);
            btnUploadBackup.disabled = false;
            btnUploadBackup.innerHTML = window.SETUP_CONFIG.i18n.restoreBackup;
        }
    });
}

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    initSetup();
    console.log('[SETUP] Setup page loaded successfully');
});
