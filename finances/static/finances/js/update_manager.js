// finances/static/finances/js/update_manager.js

class UpdateManager {
    constructor() {
        this.updateData = null;
        this.logsContent = '';
        this.i18nConfig = null;
        this.init();
    }

    init() {
        console.log('[UpdateManager] Initializing...');
        // Load i18n config from data attributes
        this.i18nConfig = document.getElementById('update-i18n-config');
        this.checkForUpdates();
        this.setupEventListeners();

        // Expose for testing
        window.forceUpdateCheck = () => this.manualCheckUpdates();
        window.updateManager = this;
        console.log('[UpdateManager] Ready');
    }

    // Helper to get translated strings from data attributes
    t(key) {
        if (!this.i18nConfig) return '';
        const dataKey = 'i18n-' + key.replace(/_/g, '-');
        return this.i18nConfig.dataset[key.replace(/-/g, '')] || this.i18nConfig.dataset[dataKey.replace(/-/g, '')] || '';
    }
    
    setupEventListeners() {
        // Manual check button in settings
        document.getElementById('manualCheckUpdates')?.addEventListener('click', () => this.manualCheckUpdates());
        
        // Modal buttons
        document.getElementById('btn-apply-local')?.addEventListener('click', () => this.applyLocalUpdates());
        document.getElementById('btn-install-github')?.addEventListener('click', () => this.installGithubUpdate());
        document.getElementById('btn-skip-local')?.addEventListener('click', () => this.skipLocalUpdate());
        document.getElementById('btn-skip')?.addEventListener('click', () => this.skipUpdate());
        document.getElementById('btn-close')?.addEventListener('click', () => this.closeAndReload());
        document.getElementById('btn-view-logs')?.addEventListener('click', () => this.showLogs());
        document.getElementById('btn-view-release')?.addEventListener('click', () => this.viewRelease());
        document.getElementById('btn-create-backup')?.addEventListener('click', () => this.createBackup());
        document.getElementById('btn-create-backup-local')?.addEventListener('click', () => this.createBackup());
        document.getElementById('close-logs')?.addEventListener('click', () => this.closeLogs());
        document.getElementById('btn-logout')?.addEventListener('click', () => this.logout());

        // Backup confirmation checkboxes
        document.getElementById('backup-confirmed')?.addEventListener('change', (e) => {
            const installBtn = document.getElementById('btn-install-github');
            if (installBtn) {
                installBtn.disabled = !e.target.checked;
            }
        });
        
        document.getElementById('backup-confirmed-local')?.addEventListener('change', (e) => {
            const applyBtn = document.getElementById('btn-apply-local');
            if (applyBtn) {
                applyBtn.disabled = !e.target.checked;
            }
        });
    }
    
    async checkForUpdates(forceShow = false) {
        try {
            console.log('[UpdateManager] Checking for updates...');
            const response = await fetch('/check-updates/');
            const data = await response.json();

            console.log('[UpdateManager] Update data:', data);

            // Update sidebar indicator if updates are available
            if (data.needs_update) {
                this.showSidebarUpdateIndicator();

                // For local updates, always show modal (blocks non-admin users)
                // For GitHub updates, only show modal if admin or if forceShow is true
                if (data.update_type === 'local' || data.is_admin || forceShow) {
                    this.updateData = data;
                    this.showUpdateModal(data);
                } else {
                    console.log('[UpdateManager] GitHub update available but user is not admin - showing sidebar indicator only');
                }
            } else {
                this.hideSidebarUpdateIndicator();
                console.log('[UpdateManager] No updates needed');
            }
        } catch (error) {
            console.error('[UpdateManager] Error checking for updates:', error);
        }
    }

    showSidebarUpdateIndicator() {
        const indicator = document.getElementById('sidebar-update-indicator');
        const versionSpan = document.getElementById('sidebar-version');
        if (indicator) {
            indicator.classList.remove('hidden');
        }
        if (versionSpan) {
            versionSpan.classList.add('text-orange-500', 'dark:text-orange-400');
            versionSpan.classList.remove('text-gray-500', 'dark:text-gray-600');
        }
    }

    hideSidebarUpdateIndicator() {
        const indicator = document.getElementById('sidebar-update-indicator');
        const versionSpan = document.getElementById('sidebar-version');
        if (indicator) {
            indicator.classList.add('hidden');
        }
        if (versionSpan) {
            versionSpan.classList.remove('text-orange-500', 'dark:text-orange-400');
            versionSpan.classList.add('text-gray-500', 'dark:text-gray-600');
        }
    }
    
    async manualCheckUpdates() {
        const btn = document.getElementById('manualCheckUpdates');
        const infoDiv = document.getElementById('online-update-info');
        const noUpdates = document.getElementById('no-updates-found');
        const hasUpdates = document.getElementById('updates-available');
        const localPending = document.getElementById('local-update-pending');
        const githubVersion = document.getElementById('github-latest-version');
        
        if (!btn) return;
        
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="material-symbols-outlined animate-spin">progress_activity</span> Checking...';
        
        try {
            const response = await fetch('/check-updates/manual/');
            const data = await response.json();
            
            console.log('[UpdateManager] Manual check data:', data);
            
            // Show info div
            if (infoDiv) {
                infoDiv.classList.remove('hidden');
                
                // Hide all messages first
                if (noUpdates) noUpdates.classList.add('hidden');
                if (hasUpdates) hasUpdates.classList.add('hidden');
                if (localPending) localPending.classList.add('hidden');
                
                if (data.needs_update) {
                    if (data.update_type === 'local') {
                        // Local updates pending
                        if (localPending) localPending.classList.remove('hidden');
                        
                        // Open modal
                        this.updateData = data;
                        this.showUpdateModal(data);
                    } else {
                        // GitHub update available
                        if (hasUpdates) hasUpdates.classList.remove('hidden');
                        if (githubVersion) githubVersion.textContent = data.target_version;
                        
                        // Open modal
                        this.updateData = data;
                        this.showUpdateModal(data);
                    }
                } else {
                    // System is up to date
                    if (noUpdates) noUpdates.classList.remove('hidden');
                    if (githubVersion) githubVersion.textContent = data.current_version;
                }
            }
        } catch (error) {
            console.error('[UpdateManager] Error checking updates:', error);
            alert(this.t('failedToCheckUpdates') || 'Failed to check for updates. Please try again.');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
    
    showUpdateModal(data) {
        console.log('[UpdateManager] Showing modal');
        const modal = document.getElementById('update-modal');
        if (!modal) {
            console.error('[UpdateManager] Modal not found');
            return;
        }
        
        // Hide all sections first
        this.hideAllSections();
        
        // Set versions
        document.getElementById('current-version').textContent = data.current_version;
        document.getElementById('target-version').textContent = data.target_version;
        
        if (data.update_type === 'local') {
            this.showLocalUpdate(data);
        } else if (data.update_type === 'github') {
            this.showGithubUpdate(data);
        }
        
        modal.classList.remove('hidden');
    }
    
    hideAllSections() {
        // Hide all possible sections
        const sections = [
            'scripts-info', 'github-info', 'container-warning',
            'backup-section', 'backup-section-local', 'update-progress', 'update-results'
        ];

        sections.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.add('hidden');
        });

        // Hide all buttons (including backup buttons)
        const buttons = [
            'btn-apply-local', 'btn-install-github', 'btn-skip', 'btn-skip-local',
            'btn-close', 'btn-view-logs', 'btn-view-release',
            'btn-create-backup', 'btn-create-backup-local', 'btn-logout'
        ];

        buttons.forEach(id => {
            const btn = document.getElementById(id);
            if (btn) btn.classList.add('hidden');
        });

        // Hide result messages
        const messages = ['success-message', 'error-message'];
        messages.forEach(id => {
            const msg = document.getElementById(id);
            if (msg) msg.classList.add('hidden');
        });
    }
    
    showLocalUpdate(data) {
        console.log('[UpdateManager] Showing local update');

        const modalIcon = document.getElementById('modal-icon');
        const updateDesc = document.getElementById('update-description');
        const scriptsInfo = document.getElementById('scripts-info');
        const scriptsList = document.getElementById('scripts-list');
        const backupSection = document.getElementById('backup-section-local');
        const btnApply = document.getElementById('btn-apply-local');
        const btnSkip = document.getElementById('btn-skip-local');
        const btnBackup = document.getElementById('btn-create-backup-local');

        if (modalIcon) {
            modalIcon.className = 'material-symbols-outlined text-4xl text-orange-500';
            modalIcon.textContent = 'construction';
        }

        // Check if user is admin
        const isAdmin = data.is_admin;

        if (!isAdmin) {
            // Non-admin user - show info only, no actions allowed
            if (updateDesc) {
                updateDesc.textContent = this.t('localUpdatePendingNonAdmin') || 'A local update is pending and must be applied before the system can be used. Only administrators can apply updates. Please contact an administrator to complete this update.';
            }

            // Show scripts info but no buttons
            if (data.has_scripts) {
                if (scriptsInfo) scriptsInfo.classList.remove('hidden');
                if (scriptsList) {
                    scriptsList.innerHTML = '';
                    data.update_scripts.forEach(script => {
                        const li = document.createElement('li');
                        li.textContent = `v${script.version}: ${script.description}`;
                        scriptsList.appendChild(li);
                    });
                }
            }

            // Show logout button for non-admin users
            const btnLogout = document.getElementById('btn-logout');
            if (btnLogout) {
                btnLogout.classList.remove('hidden');
            }

            // Hide all other action buttons for non-admin
            return;
        }

        // Admin user - show full update interface
        if (data.has_scripts) {
            if (updateDesc) {
                updateDesc.textContent = this.t('localUpdatesAvailable') || 'Local updates are available and must be applied before continuing.';
            }
            if (scriptsInfo) scriptsInfo.classList.remove('hidden');
            if (scriptsList) {
                scriptsList.innerHTML = '';
                data.update_scripts.forEach(script => {
                    const li = document.createElement('li');
                    li.textContent = `v${script.version}: ${script.description}`;
                    scriptsList.appendChild(li);
                });
            }
        } else {
            if (updateDesc) {
                updateDesc.textContent = this.t('systemFilesUpdated') || 'System files have been updated. Database migrations will be applied.';
            }
        }

        // Show backup section and buttons (admin only)
        if (backupSection) backupSection.classList.remove('hidden');
        if (btnBackup) btnBackup.classList.remove('hidden');
        if (btnApply) {
            btnApply.classList.remove('hidden');
            btnApply.disabled = true; // Disabled until backup confirmed
        }
        // Note: btnSkip (Remind Me Later) removed for local updates
    }
    
    showGithubUpdate(data) {
        console.log('[UpdateManager] Showing GitHub update');

        const modalIcon = document.getElementById('modal-icon');
        const updateDesc = document.getElementById('update-description');
        const githubInfo = document.getElementById('github-info');
        const releaseName = document.getElementById('release-name');
        const releaseNotes = document.getElementById('release-notes');
        const releaseDate = document.getElementById('release-date');
        const readMoreLink = document.getElementById('read-more-link');
        const containerWarning = document.getElementById('container-warning');
        const backupSection = document.getElementById('backup-section');
        const btnSkip = document.getElementById('btn-skip');
        const btnInstall = document.getElementById('btn-install-github');
        const btnViewRelease = document.getElementById('btn-view-release');
        const btnCreateBackup = document.getElementById('btn-create-backup');

        if (modalIcon) {
            modalIcon.className = 'material-symbols-outlined text-4xl text-green-500';
            modalIcon.textContent = 'cloud_download';
        }

        if (updateDesc) {
            updateDesc.textContent = this.t('githubVersionAvailable') || 'A new version is available on GitHub!';
        }

        if (githubInfo) githubInfo.classList.remove('hidden');
        if (releaseName) {
            releaseName.textContent = data.github_release.name || `Version ${data.target_version}`;
        }

        // Limit release notes to 5 lines with fade effect and read more link
        if (releaseNotes) {
            const notes = data.github_release.body || 'No release notes available.';
            const lines = notes.split('\n');
            const maxLines = 5;

            if (lines.length > maxLines) {
                const limitedNotes = lines.slice(0, maxLines).join('\n');
                const formattedNotes = this.formatMarkdown(limitedNotes);

                // Create container with fade effect
                releaseNotes.innerHTML = `
                    <div class="relative max-h-32 overflow-hidden">
                        <div>${formattedNotes}</div>
                        <div class="absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-green-50 dark:from-green-900/20 to-transparent"></div>
                    </div>
                `;

                // Show read more link
                if (readMoreLink) {
                    readMoreLink.href = data.github_release.html_url;
                    readMoreLink.classList.remove('hidden');
                }
            } else {
                releaseNotes.innerHTML = this.formatMarkdown(notes);
                if (readMoreLink) {
                    readMoreLink.classList.add('hidden');
                }
            }
        }

        if (releaseDate) {
            const date = new Date(data.github_release.published_at);
            releaseDate.textContent = date.toLocaleDateString();
        }

        if (btnViewRelease) btnViewRelease.classList.remove('hidden');

        // Check if user is admin
        const isAdmin = data.is_admin;

        if (data.requires_container) {
            // Container update required - manual process
            if (containerWarning) containerWarning.classList.remove('hidden');
            if (btnInstall) btnInstall.classList.add('hidden');
            if (backupSection) backupSection.classList.add('hidden');
            if (btnCreateBackup) btnCreateBackup.classList.add('hidden');

            // Show OK button for container updates (admin only)
            if (isAdmin && btnSkip) {
                btnSkip.textContent = this.t('buttonOk') || 'OK';
                btnSkip.classList.remove('hidden');
            }
        } else if (isAdmin) {
            // Show Skip button for regular updates (admin only)
            if (btnSkip) {
                btnSkip.textContent = this.t('buttonSkipUpdate') || 'Skip Update';
                btnSkip.classList.remove('hidden');
            }
            // Admin user - can install via web interface
            if (backupSection) backupSection.classList.remove('hidden');
            if (btnCreateBackup) btnCreateBackup.classList.remove('hidden');
            if (btnInstall) {
                btnInstall.classList.remove('hidden');
                btnInstall.disabled = true; // Disabled until backup confirmed
            }
        } else {
            // Non-admin user - show information only
            if (updateDesc) {
                updateDesc.textContent = this.t('githubUpdateNonAdmin') || 'A new version is available on GitHub. Only administrators can install updates. Please contact an administrator to apply this update.';
            }
            // Hide backup and install options for non-admin
            if (backupSection) backupSection.classList.add('hidden');
            if (btnCreateBackup) btnCreateBackup.classList.add('hidden');
            if (btnInstall) btnInstall.classList.add('hidden');
        }
    }
    
    formatMarkdown(text) {
        return text
            .replace(/^### (.*$)/gim, '<h3 class="font-semibold mt-3 mb-1">$1</h3>')
            .replace(/^## (.*$)/gim, '<h2 class="font-bold text-lg mt-4 mb-2">$1</h2>')
            .replace(/^# (.*$)/gim, '<h1 class="font-bold text-xl mt-4 mb-2">$1</h1>')
            .replace(/^\* (.*$)/gim, '<li class="ml-4">$1</li>')
            .replace(/^\- (.*$)/gim, '<li class="ml-4">$1</li>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>');
    }
    
    async applyLocalUpdates() {
        console.log('[UpdateManager] Applying local updates...');
        
        const backupConfirmed = document.getElementById('backup-confirmed-local');
        if (!backupConfirmed || !backupConfirmed.checked) {
            alert(this.t('pleaseConfirmBackup') || 'Please confirm that you have created a backup before proceeding.');
            return;
        }
        
        const progressSection = document.getElementById('update-progress');
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-text');
        const progressTitle = document.getElementById('progress-title');
        const btnApply = document.getElementById('btn-apply-local');
        const btnSkip = document.getElementById('btn-skip-local');
        const backupSection = document.getElementById('backup-section-local');
        
        if (btnApply) btnApply.classList.add('hidden');
        if (btnSkip) btnSkip.classList.add('hidden');
        if (backupSection) backupSection.classList.add('hidden');
        if (progressSection) progressSection.classList.remove('hidden');
        if (progressTitle) progressTitle.textContent = this.t('applyingUpdates') || 'Applying Updates...';

        try {
            if (progressBar) progressBar.style.width = '10%';
            if (progressText) progressText.textContent = this.t('preparingUpdate') || 'Preparing update...';

            const requestBody = this.updateData.has_scripts ? {
                scripts: this.updateData.update_scripts
            } : {};
            
            console.log('[UpdateManager] Sending request with body:', requestBody);
            
            const response = await fetch('/apply-local-updates/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCookie('csrftoken')
                },
                body: JSON.stringify(requestBody)
            });

            if (progressBar) progressBar.style.width = '50%';
            if (progressText) progressText.textContent = this.t('applyingUpdatesProgress') || 'Applying updates...';

            const data = await response.json();
            console.log('[UpdateManager] Update response:', data);

            if (progressBar) progressBar.style.width = '100%';
            if (progressText) progressText.textContent = this.t('updateComplete') || 'Update complete!';

            this.logsContent = this.formatLogs(data);

            if (data.success) {
                this.showSuccessWithReload(this.t('updatesAppliedSuccess') || 'Updates applied successfully! Waiting for server to restart...');
            } else {
                this.showError(data.error || (this.t('updateFailed') || 'Update failed. Check logs for details.'));
            }
        } catch (error) {
            console.error('[UpdateManager] Error applying updates:', error);
            this.showError((this.t('failedToApplyUpdates') || 'Failed to apply updates') + ': ' + error.message);
        }
    }
    
    async installGithubUpdate() {
        console.log('[UpdateManager] Installing GitHub update...');
        console.log('[UpdateManager] Full updateData:', JSON.stringify(this.updateData, null, 2));

        // Validate updateData
        if (!this.updateData) {
            console.error('[UpdateManager] No updateData available!');
            this.showError('Update data is missing. Please refresh and try again.');
            return;
        }

        if (!this.updateData.github_release) {
            console.error('[UpdateManager] No github_release in updateData!');
            this.showError('GitHub release data is missing. Please refresh and try again.');
            return;
        }

        if (!this.updateData.github_release.zipball_url) {
            console.error('[UpdateManager] No zipball_url in github_release!');
            this.showError('Download URL is missing. Please refresh and try again.');
            return;
        }

        // Get target_version from either updateData or github_release
        const targetVersion = this.updateData.target_version || this.updateData.github_release.version;

        if (!targetVersion) {
            console.error('[UpdateManager] No target_version found!');
            console.error('[UpdateManager] updateData.target_version:', this.updateData.target_version);
            console.error('[UpdateManager] github_release.version:', this.updateData.github_release.version);
            this.showError('Target version is missing. Please refresh and try again.');
            return;
        }

        console.log('[UpdateManager] Using target_version:', targetVersion);

        const backupConfirmed = document.getElementById('backup-confirmed');
        if (!backupConfirmed || !backupConfirmed.checked) {
            alert(this.t('pleaseConfirmBackup') || 'Please confirm that you have created a backup before proceeding.');
            return;
        }

        const progressSection = document.getElementById('update-progress');
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-text');
        const progressTitle = document.getElementById('progress-title');
        const btnInstall = document.getElementById('btn-install-github');
        const btnSkip = document.getElementById('btn-skip');
        const backupSection = document.getElementById('backup-section');

        if (btnInstall) btnInstall.classList.add('hidden');
        if (btnSkip) btnSkip.classList.add('hidden');
        if (backupSection) backupSection.classList.add('hidden');
        if (progressSection) progressSection.classList.remove('hidden');
        if (progressTitle) progressTitle.textContent = this.t('installingGithubUpdate') || 'Installing GitHub Update...';

        try {
            if (progressBar) progressBar.style.width = '10%';
            if (progressText) progressText.textContent = this.t('downloadingRelease') || 'Downloading release...';

            const requestBody = {
                zipball_url: this.updateData.github_release.zipball_url,
                target_version: targetVersion
            };

            console.log('[UpdateManager] Request body:', requestBody);

            const response = await fetch('/download-github-update/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCookie('csrftoken')
                },
                body: JSON.stringify(requestBody)
            });

            console.log('[UpdateManager] Response status:', response.status);
            console.log('[UpdateManager] Response ok:', response.ok);

            if (progressBar) progressBar.style.width = '50%';
            if (progressText) progressText.textContent = this.t('extractingFiles') || 'Extracting files...';

            const data = await response.json();
            console.log('[UpdateManager] GitHub update response:', data);

            if (progressBar) progressBar.style.width = '100%';
            if (progressText) progressText.textContent = this.t('updateComplete') || 'Update complete!';

            // Store logs regardless of success/failure
            this.logsContent = this.formatGithubLogs(data);

            if (data.success) {
                this.showSuccessWithReload(this.t('githubUpdateSuccess') || 'GitHub update installed successfully! Waiting for server to restart...');
            } else {
                this.showError(data.error || (this.t('updateFailed') || 'Update failed. Check logs for details.'));
            }
        } catch (error) {
            console.error('[UpdateManager] Error installing GitHub update:', error);

            // Store error in logs
            this.logsContent = `=== GitHub Update Error ===\n\nError: ${error.message}\n\nStack Trace:\n${error.stack || 'No stack trace available'}`;

            this.showError((this.t('failedToInstallUpdate') || 'Failed to install update') + ': ' + error.message);
        }
    }
    
    async createBackup() {
        const btn = document.getElementById('btn-create-backup') || document.getElementById('btn-create-backup-local');
        if (!btn) return;
        
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="material-symbols-outlined animate-spin">progress_activity</span> Creating...';
        
        try {
            const response = await fetch('/create-backup/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCookie('csrftoken')
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                window.location.href = `/download-backup/${data.filename}/`;
                alert(this.t('backupCreatedSuccessfully') || 'Backup created successfully! File will be downloaded.');
            } else {
                alert((this.t('failedToCreateBackup') || 'Failed to create backup: ') + data.error);
            }
        } catch (error) {
            console.error('[UpdateManager] Error creating backup:', error);
            alert((this.t('failedToCreateBackup') || 'Failed to create backup: ') + error.message);
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }

    async skipLocalUpdate() {
        alert(this.t('localUpdatesCannotBeSkipped') || 'Local updates cannot be skipped. They are required for the system to function correctly.');
    }

    async skipUpdate() {
        if (!confirm(this.t('confirmSkipUpdate') || 'Are you sure you want to skip this update? You won\'t be notified about this version again until a newer version is released.')) {
            return;
        }

        try {
            const response = await fetch('/skip-updates/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCookie('csrftoken')
                },
                body: JSON.stringify({
                    update_type: this.updateData.update_type,
                    version: this.updateData.target_version
                })
            });

            const data = await response.json();

            if (data.success) {
                document.getElementById('update-modal').classList.add('hidden');
            } else {
                alert((this.t('failedToSkipUpdate2') || 'Failed to skip update: ') + (data.error || this.t('unknownError') || 'Unknown error'));
            }
        } catch (error) {
            console.error('[UpdateManager] Error skipping update:', error);
            alert(this.t('failedToSkipUpdate') || 'Failed to skip update. Please try again.');
        }
    }
    
    showSuccess(message) {
        const progressSection = document.getElementById('update-progress');
        const resultsSection = document.getElementById('update-results');
        const successMsg = document.getElementById('success-message');
        const successDetails = document.getElementById('success-details');
        const btnClose = document.getElementById('btn-close');

        if (progressSection) progressSection.classList.add('hidden');
        if (resultsSection) resultsSection.classList.remove('hidden');
        if (successMsg) successMsg.classList.remove('hidden');
        if (successDetails) successDetails.textContent = message;
        if (btnClose) btnClose.classList.remove('hidden');
    }

    showSuccessWithReload(message) {
        const progressSection = document.getElementById('update-progress');
        const resultsSection = document.getElementById('update-results');
        const successMsg = document.getElementById('success-message');
        const successDetails = document.getElementById('success-details');

        if (progressSection) progressSection.classList.add('hidden');
        if (resultsSection) resultsSection.classList.remove('hidden');
        if (successMsg) successMsg.classList.remove('hidden');

        // Add spinner and message
        if (successDetails) {
            successDetails.innerHTML = `
                <div class="flex items-center gap-3">
                    <div class="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-green-600"></div>
                    <span>${message}</span>
                </div>
            `;
        }

        // Start checking if server is back up
        this.waitForServerAndReload();
    }

    async waitForServerAndReload() {
        const maxAttempts = 120; // Try for up to 2 minutes (doubled from 60s)
        const delayBetweenAttempts = 1000; // 1 second
        let consecutiveSuccess = 0;
        const requiredConsecutiveSuccess = 2; // Require 2 successful checks to ensure stability

        console.log('[UpdateManager] Starting health check polling...');

        for (let attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                // Try to fetch a lightweight endpoint with timeout
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout

                const response = await fetch('/api/health-check/', {
                    method: 'GET',
                    cache: 'no-store',
                    signal: controller.signal,
                    headers: {
                        'Cache-Control': 'no-cache, no-store, must-revalidate',
                        'Pragma': 'no-cache',
                        'Expires': '0'
                    }
                });

                clearTimeout(timeoutId);

                if (response.ok) {
                    const data = await response.json();
                    consecutiveSuccess++;
                    console.log(`[UpdateManager] Server responded OK (${consecutiveSuccess}/${requiredConsecutiveSuccess}) - attempt ${attempt}/${maxAttempts}`, data);

                    // Require multiple consecutive successful responses to ensure server is stable
                    if (consecutiveSuccess >= requiredConsecutiveSuccess) {
                        console.log(`[UpdateManager] Server is stable and ready after ${attempt} attempts`);
                        // Wait 1 more second for good measure
                        await new Promise(resolve => setTimeout(resolve, 1000));
                        // Server is back and stable, reload the page
                        location.reload();
                        return;
                    }
                } else {
                    consecutiveSuccess = 0; // Reset counter on failure
                    console.log(`[UpdateManager] Server responded with status ${response.status}, waiting... attempt ${attempt}/${maxAttempts}`);
                }
            } catch (error) {
                consecutiveSuccess = 0; // Reset counter on error
                // Server not ready yet, continue waiting
                if (error.name === 'AbortError') {
                    console.log(`[UpdateManager] Health check timeout, server still starting... attempt ${attempt}/${maxAttempts}`);
                } else {
                    console.log(`[UpdateManager] Waiting for server... attempt ${attempt}/${maxAttempts}`, error.message);
                }
            }

            // Wait before next attempt
            await new Promise(resolve => setTimeout(resolve, delayBetweenAttempts));
        }

        // If we get here, server didn't come back up in time
        const successDetails = document.getElementById('success-details');
        if (successDetails) {
            const takingLongerMsg = this.t('serverRestartTakingLonger') || 'Server is taking longer than expected to restart.';
            const waitMsg = this.t('waitAndClickToReload') || 'Please wait a moment and then';
            const clickMsg = this.t('clickHereToReload') || 'click here to reload';

            successDetails.innerHTML = `
                <div>
                    <p class="text-yellow-600 dark:text-yellow-400 mb-2">${takingLongerMsg}</p>
                    <p class="text-sm">${waitMsg} <button onclick="location.reload()" class="text-green-600 hover:text-green-700 underline font-medium">${clickMsg}</button>.</p>
                </div>
            `;
        }
    }

    showError(message) {
        const progressSection = document.getElementById('update-progress');
        const resultsSection = document.getElementById('update-results');
        const errorMsg = document.getElementById('error-message');
        const errorDetails = document.getElementById('error-details');
        const btnViewLogs = document.getElementById('btn-view-logs');
        
        if (progressSection) progressSection.classList.add('hidden');
        if (resultsSection) resultsSection.classList.remove('hidden');
        if (errorMsg) errorMsg.classList.remove('hidden');
        if (errorDetails) errorDetails.textContent = message;
        if (btnViewLogs) btnViewLogs.classList.remove('hidden');
    }
    
    formatLogs(data) {
        let logs = '=== Update Process Logs ===\n\n';

        if (data.results) {
            data.results.forEach(result => {
                // Use 'filename' instead of 'script' (backend sends 'filename')
                const scriptName = result.filename || result.script || 'Unknown Script';
                logs += `\n=== ${scriptName} ===\n`;
                logs += `Status: ${result.status}\n`;
                if (result.output) {
                    logs += `Output:\n${result.output}\n`;
                }
                if (result.error) {
                    logs += `Error: ${result.error}\n`;
                    if (result.traceback) {
                        logs += `\nTraceback:\n${result.traceback}\n`;
                    }
                }
            });
        }
        if (data.traceback) {
            logs += `\n=== Full Traceback ===\n${data.traceback}`;
        }
        return logs || 'No detailed logs available';
    }

    formatGithubLogs(data) {
        let logs = '=== GitHub Update Process Logs ===\n\n';

        if (data.success) {
            logs += 'Status: SUCCESS\n';
            logs += `Message: ${data.message || 'Update completed successfully'}\n`;
            if (data.new_version) {
                logs += `New Version: ${data.new_version}\n`;
            }
            logs += '\n=== Update Process Details ===\n';
            if (data.logs) {
                logs += data.logs;
            } else {
                logs += 'No detailed logs available';
            }
        } else {
            logs += 'Status: FAILED\n';
            logs += `Error: ${data.error || 'Unknown error'}\n`;

            logs += '\n=== Update Process Details ===\n';
            if (data.logs) {
                logs += data.logs;
            } else if (data.traceback) {
                logs += `Server Traceback:\n${data.traceback}`;
            } else {
                logs += 'No detailed logs available';
            }
        }

        return logs;
    }
    
    showLogs() {
        console.log('[UpdateManager] showLogs called');
        console.log('[UpdateManager] logsContent:', this.logsContent);
        console.log('[UpdateManager] logsContent length:', this.logsContent.length);

        const logsModal = document.getElementById('logs-modal');
        const logsContent = document.getElementById('logs-content');

        if (!logsModal) {
            console.error('[UpdateManager] logs-modal element not found!');
            alert(this.t('logsModalNotFound') || 'Logs modal element not found in the page.');
            return;
        }

        if (!logsContent) {
            console.error('[UpdateManager] logs-content element not found!');
            alert(this.t('logsContentNotFound') || 'Logs content element not found in the page.');
            return;
        }

        if (!this.logsContent || this.logsContent.length === 0) {
            console.warn('[UpdateManager] No logs available');
            logsContent.textContent = this.t('noLogsAvailable') || 'No logs available yet. Please apply an update first.';
        } else {
            logsContent.textContent = this.logsContent;
        }

        logsModal.classList.remove('hidden');
        console.log('[UpdateManager] Logs modal shown');
    }
    
    closeLogs() {
        document.getElementById('logs-modal').classList.add('hidden');
    }
    
    viewRelease() {
        if (this.updateData && this.updateData.github_release) {
            window.open(this.updateData.github_release.html_url, '_blank');
        }
    }
    
    closeAndReload() {
        location.reload();
    }

    async logout() {
        console.log('[UpdateManager] Logging out user');

        try {
            // Create form and submit POST request
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = '/auth/logout/';

            // Add CSRF token
            const csrfToken = this.getCookie('csrftoken');
            if (csrfToken) {
                const csrfInput = document.createElement('input');
                csrfInput.type = 'hidden';
                csrfInput.name = 'csrfmiddlewaretoken';
                csrfInput.value = csrfToken;
                form.appendChild(csrfInput);
            }

            // Add form to document and submit
            document.body.appendChild(form);
            form.submit();
        } catch (error) {
            console.error('[UpdateManager] Error during logout:', error);
            // Fallback: try direct navigation
            window.location.href = '/auth/logout/';
        }
    }

    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
}

// Initialize when DOM is ready, but only if admin modal is not present
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        const adminModal = document.getElementById('admin-warning-modal');
        if (!adminModal) {
            window.updateManager = new UpdateManager();
        }
    });
} else {
    const adminModal = document.getElementById('admin-warning-modal');
    if (!adminModal) {
        window.updateManager = new UpdateManager();
    }
}