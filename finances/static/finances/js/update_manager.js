// finances/static/finances/js/update_manager.js

class UpdateManager {
    constructor() {
        this.updateData = null;
        this.logsContent = '';
        this.init();
    }
    
    init() {
        console.log('[UpdateManager] Initializing...');
        this.checkForUpdates();
        this.setupEventListeners();
        
        // Expose for testing
        window.forceUpdateCheck = () => this.manualCheckUpdates();
        window.updateManager = this;
        console.log('[UpdateManager] Ready');
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
            
            if (data.needs_update || forceShow) {
                this.updateData = data;
                this.showUpdateModal(data);
            } else {
                console.log('[UpdateManager] No updates needed');
            }
        } catch (error) {
            console.error('[UpdateManager] Error checking for updates:', error);
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
            alert('Failed to check for updates. Please try again.');
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
        
        // Hide all buttons
        const buttons = [
            'btn-apply-local', 'btn-install-github', 'btn-skip', 'btn-skip-local',
            'btn-close', 'btn-view-logs', 'btn-view-release', 'btn-create-backup',
            'btn-create-backup-local'
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
        
        if (data.has_scripts) {
            if (updateDesc) {
                updateDesc.textContent = 'Local updates are available and must be applied before continuing.';
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
                updateDesc.textContent = 'System files have been updated. Database migrations will be applied.';
            }
        }
        
        // Show backup section and buttons
        if (backupSection) backupSection.classList.remove('hidden');
        if (btnBackup) btnBackup.classList.remove('hidden');
        if (btnApply) {
            btnApply.classList.remove('hidden');
            btnApply.disabled = true; // Disabled until backup confirmed
        }
        if (btnSkip) btnSkip.classList.remove('hidden');
    }
    
    showGithubUpdate(data) {
        console.log('[UpdateManager] Showing GitHub update');
        
        const modalIcon = document.getElementById('modal-icon');
        const updateDesc = document.getElementById('update-description');
        const githubInfo = document.getElementById('github-info');
        const releaseName = document.getElementById('release-name');
        const releaseNotes = document.getElementById('release-notes');
        const releaseDate = document.getElementById('release-date');
        const containerWarning = document.getElementById('container-warning');
        const backupSection = document.getElementById('backup-section');
        const btnSkip = document.getElementById('btn-skip');
        const btnInstall = document.getElementById('btn-install-github');
        const btnViewRelease = document.getElementById('btn-view-release');
        
        if (modalIcon) {
            modalIcon.className = 'material-symbols-outlined text-4xl text-green-500';
            modalIcon.textContent = 'cloud_download';
        }
        
        if (updateDesc) {
            updateDesc.textContent = 'A new version is available on GitHub!';
        }
        
        if (githubInfo) githubInfo.classList.remove('hidden');
        if (releaseName) {
            releaseName.textContent = data.github_release.name || `Version ${data.target_version}`;
        }
        
        // Limit release notes to 7 lines with fade effect
        if (releaseNotes) {
            const notes = data.github_release.body || 'No release notes available.';
            const lines = notes.split('\n');
            const maxLines = 7;
            
            if (lines.length > maxLines) {
                const limitedNotes = lines.slice(0, maxLines).join('\n');
                const formattedNotes = this.formatMarkdown(limitedNotes);
                
                // Create container with fade effect
                releaseNotes.innerHTML = `
                    <div class="relative max-h-48 overflow-hidden">
                        <div>${formattedNotes}</div>
                        <div class="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-white dark:from-gray-800 to-transparent"></div>
                    </div>
                `;
            } else {
                releaseNotes.innerHTML = this.formatMarkdown(notes);
            }
        }
        
        if (releaseDate) {
            const date = new Date(data.github_release.published_at);
            releaseDate.textContent = date.toLocaleDateString();
        }
        
        if (btnViewRelease) btnViewRelease.classList.remove('hidden');
        if (btnSkip) btnSkip.classList.remove('hidden');
        
        if (data.requires_container) {
            // Container update required - manual process
            if (containerWarning) containerWarning.classList.remove('hidden');
            if (btnInstall) btnInstall.classList.add('hidden');
            if (backupSection) backupSection.classList.add('hidden');
        } else {
            // Can install via web interface
            if (backupSection) backupSection.classList.remove('hidden');
            if (btnInstall) {
                btnInstall.classList.remove('hidden');
                btnInstall.disabled = true; // Disabled until backup confirmed
            }
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
            alert('Please confirm that you have created a backup before proceeding.');
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
        if (progressTitle) progressTitle.textContent = 'Applying Updates...';
        
        try {
            if (progressBar) progressBar.style.width = '10%';
            if (progressText) progressText.textContent = 'Preparing update...';
            
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
            if (progressText) progressText.textContent = 'Applying updates...';
            
            const data = await response.json();
            console.log('[UpdateManager] Update response:', data);
            
            if (progressBar) progressBar.style.width = '100%';
            if (progressText) progressText.textContent = 'Update complete!';
            
            this.logsContent = this.formatLogs(data);
            
            if (data.success) {
                this.showSuccess('Updates applied successfully! The page will reload in 3 seconds.');
                setTimeout(() => location.reload(), 3000);
            } else {
                this.showError(data.error || 'Update failed. Check logs for details.');
            }
        } catch (error) {
            console.error('[UpdateManager] Error applying updates:', error);
            this.showError('Failed to apply updates: ' + error.message);
        }
    }
    
    async installGithubUpdate() {
        console.log('[UpdateManager] Installing GitHub update...');
        
        const backupConfirmed = document.getElementById('backup-confirmed');
        if (!backupConfirmed || !backupConfirmed.checked) {
            alert('Please confirm that you have created a backup before proceeding.');
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
        if (progressTitle) progressTitle.textContent = 'Installing GitHub Update...';
        
        try {
            if (progressBar) progressBar.style.width = '10%';
            if (progressText) progressText.textContent = 'Downloading release...';
            
            const response = await fetch('/download-github-update/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCookie('csrftoken')
                },
                body: JSON.stringify({
                    zipball_url: this.updateData.github_release.zipball_url
                })
            });
            
            if (progressBar) progressBar.style.width = '50%';
            if (progressText) progressText.textContent = 'Extracting files...';
            
            const data = await response.json();
            console.log('[UpdateManager] GitHub update response:', data);
            
            if (progressBar) progressBar.style.width = '100%';
            if (progressText) progressText.textContent = 'Update complete!';
            
            if (data.success) {
                this.showSuccess('GitHub update installed successfully! The page will reload in 3 seconds.');
                setTimeout(() => location.reload(), 3000);
            } else {
                this.showError(data.error || 'Update failed.');
            }
        } catch (error) {
            console.error('[UpdateManager] Error installing GitHub update:', error);
            this.showError('Failed to install update: ' + error.message);
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
                alert('Backup created successfully! File will be downloaded.');
            } else {
                alert('Failed to create backup: ' + data.error);
            }
        } catch (error) {
            console.error('[UpdateManager] Error creating backup:', error);
            alert('Failed to create backup: ' + error.message);
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
    
    async skipLocalUpdate() {
        alert('Local updates cannot be skipped. They are required for the system to function correctly.');
    }
    
    async skipUpdate() {
        if (!confirm('Are you sure you want to skip this update? You can update later from settings.')) {
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
                    update_type: this.updateData.update_type
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                document.getElementById('update-modal').classList.add('hidden');
            }
        } catch (error) {
            console.error('[UpdateManager] Error skipping update:', error);
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
                logs += `\n=== ${result.script} ===\n`;
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
    
    showLogs() {
        document.getElementById('logs-modal').classList.remove('hidden');
        document.getElementById('logs-content').textContent = this.logsContent;
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

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        new UpdateManager();
    });
} else {
    new UpdateManager();
}