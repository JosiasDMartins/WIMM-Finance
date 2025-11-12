// finances/static/finances/js/update_manager.js

class UpdateManager {
    constructor() {
        this.updateData = null;
        this.init();
    }
    
    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.checkForUpdates();
            this.setupEventListeners();
        });
    }
    
    setupEventListeners() {
        document.getElementById('btn-apply-local')?.addEventListener('click', () => this.applyLocalUpdates());
        document.getElementById('btn-install-github')?.addEventListener('click', () => this.installGithubUpdate());
        document.getElementById('btn-skip')?.addEventListener('click', () => this.skipUpdate());
        document.getElementById('btn-close')?.addEventListener('click', () => this.closeAndReload());
        document.getElementById('btn-view-logs')?.addEventListener('click', () => this.showLogs());
        document.getElementById('btn-view-release')?.addEventListener('click', () => this.viewRelease());
        document.getElementById('btn-create-backup')?.addEventListener('click', () => this.createBackup());
        document.getElementById('close-logs')?.addEventListener('click', () => this.closeLogs());
        
        // Enable/disable install button based on backup checkbox
        document.getElementById('backup-confirmed')?.addEventListener('change', (e) => {
            const installBtn = document.getElementById('btn-install-github');
            if (installBtn) {
                installBtn.disabled = !e.target.checked;
            }
        });
    }
    
    async checkForUpdates() {
        try {
            const response = await fetch('/check-updates/');
            const data = await response.json();
            
            if (data.needs_update) {
                this.updateData = data;
                this.showUpdateModal(data);
            }
        } catch (error) {
            console.error('Error checking for updates:', error);
        }
    }
    
    showUpdateModal(data) {
        const modal = document.getElementById('update-modal');
        
        document.getElementById('current-version').textContent = data.current_version;
        document.getElementById('target-version').textContent = data.target_version;
        
        if (data.update_type === 'local') {
            this.showLocalUpdate(data);
        } else if (data.update_type === 'github') {
            this.showGithubUpdate(data);
        }
        
        modal.classList.remove('hidden');
    }
    
    showLocalUpdate(data) {
        const modalIcon = document.getElementById('modal-icon');
        const updateDesc = document.getElementById('update-description');
        const scriptsInfo = document.getElementById('scripts-info');
        const scriptsList = document.getElementById('scripts-list');
        const btnApply = document.getElementById('btn-apply-local');
        
        modalIcon.className = 'material-symbols-outlined text-4xl text-orange-500';
        modalIcon.textContent = 'construction';
        
        updateDesc.textContent = 'Local updates are available and must be applied before continuing.';
        
        if (data.has_scripts) {
            scriptsInfo.classList.remove('hidden');
            scriptsList.innerHTML = '';
            data.update_scripts.forEach(script => {
                const li = document.createElement('li');
                li.textContent = `v${script.version}: ${script.description}`;
                scriptsList.appendChild(li);
            });
        }
        
        btnApply.classList.remove('hidden');
    }
    
    showGithubUpdate(data) {
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
        
        modalIcon.className = 'material-symbols-outlined text-4xl text-green-500';
        modalIcon.textContent = 'cloud_download';
        
        updateDesc.textContent = 'A new version is available on GitHub!';
        
        githubInfo.classList.remove('hidden');
        releaseName.textContent = data.github_release.name || `Version ${data.target_version}`;
        
        // Format release notes (markdown to basic HTML)
        const notes = data.github_release.body || 'No release notes available.';
        releaseNotes.innerHTML = this.formatMarkdown(notes);
        
        // Format date
        const date = new Date(data.github_release.published_at);
        releaseDate.textContent = date.toLocaleDateString();
        
        btnViewRelease.classList.remove('hidden');
        btnSkip.classList.remove('hidden');
        
        if (data.requires_container) {
            // Container update required - only show warning and link to release
            containerWarning.classList.remove('hidden');
            btnInstall.classList.add('hidden');
            backupSection.classList.add('hidden');
        } else {
            // Can install directly
            backupSection.classList.remove('hidden');
            btnInstall.classList.remove('hidden');
            btnInstall.disabled = true; // Disabled until backup confirmed
        }
    }
    
    formatMarkdown(text) {
        // Basic markdown formatting
        return text
            .replace(/^### (.*$)/gim, '<h3 class="font-semibold mt-3 mb-1">$1</h3>')
            .replace(/^## (.*$)/gim, '<h2 class="font-bold text-lg mt-4 mb-2">$1</h2>')
            .replace(/^# (.*$)/gim, '<h1 class="font-bold text-xl mt-4 mb-2">$1</h1>')
            .replace(/^\* (.*$)/gim, '<li class="ml-4">$1</li>')
            .replace(/^\- (.*$)/gim, '<li class="ml-4">$1</li>')
            .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
            .replace(/\n\n/g, '</p><p class="mt-2">')
            .replace(/\n/g, '<br>');
    }
    
    async applyLocalUpdates() {
        const progressSection = document.getElementById('update-progress');
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-text');
        const progressTitle = document.getElementById('progress-title');
        const btnApply = document.getElementById('btn-apply-local');
        const mainContent = document.getElementById('main-content');
        
        btnApply.classList.add('hidden');
        progressSection.classList.remove('hidden');
        progressTitle.textContent = 'Applying Local Updates...';
        
        try {
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress = Math.min(progress + 10, 90);
                progressBar.style.width = progress + '%';
                progressText.textContent = `Processing... ${progress}%`;
            }, 500);
            
            const response = await fetch('/apply-local-updates/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCookie('csrftoken')
                },
                body: JSON.stringify({
                    scripts: this.updateData.update_scripts
                })
            });
            
            clearInterval(progressInterval);
            progressBar.style.width = '100%';
            
            const data = await response.json();
            this.showResults(data);
            
        } catch (error) {
            this.showError('Network error: ' + error.message);
        }
    }
    
    async installGithubUpdate() {
        const backupConfirmed = document.getElementById('backup-confirmed').checked;
        
        if (!backupConfirmed) {
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
        
        btnInstall.classList.add('hidden');
        btnSkip.classList.add('hidden');
        backupSection.classList.add('hidden');
        progressSection.classList.remove('hidden');
        progressTitle.textContent = 'Installing GitHub Update...';
        
        try {
            progressBar.style.width = '10%';
            progressText.textContent = 'Starting download...';
            
            const response = await fetch('/download-github-update/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCookie('csrftoken')
                },
                body: JSON.stringify({
                    zipball_url: this.updateData.github_release.zipball_url,
                    target_version: this.updateData.target_version
                })
            });
            
            progressBar.style.width = '100%';
            progressText.textContent = 'Installation complete!';
            
            const data = await response.json();
            
            if (data.success) {
                this.showSuccess(data.message);
            } else {
                this.showError(data.error || 'Installation failed');
            }
            
        } catch (error) {
            this.showError('Network error: ' + error.message);
        }
    }
    
    async createBackup() {
        const btn = document.getElementById('btn-create-backup');
        const originalText = btn.innerHTML;
        
        btn.disabled = true;
        btn.innerHTML = '<span class="material-symbols-outlined animate-spin">progress_activity</span> Creating backup...';
        
        try {
            const response = await fetch('/create-backup/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCookie('csrftoken')
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Download the backup
                window.location.href = data.download_url;
                
                btn.innerHTML = '<span class="material-symbols-outlined">check_circle</span> Backup Downloaded';
                btn.classList.remove('bg-amber-600', 'hover:bg-amber-700');
                btn.classList.add('bg-green-600');
                
                // Enable the backup confirmation checkbox
                document.getElementById('backup-confirmed').disabled = false;
            } else {
                alert('Backup failed: ' + data.error);
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        } catch (error) {
            alert('Error creating backup: ' + error.message);
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
    
    async skipUpdate() {
        if (!confirm('Are you sure you want to skip this update? You can update later from the settings.')) {
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
            console.error('Error skipping update:', error);
        }
    }
    
    showResults(data) {
        const progressSection = document.getElementById('update-progress');
        const resultsSection = document.getElementById('update-results');
        const successMsg = document.getElementById('success-message');
        const successDetails = document.getElementById('success-details');
        const errorMsg = document.getElementById('error-message');
        const errorDetails = document.getElementById('error-details');
        const resultsDetailsDiv = document.getElementById('results-details');
        const btnClose = document.getElementById('btn-close');
        const btnViewLogs = document.getElementById('btn-view-logs');
        
        progressSection.classList.add('hidden');
        resultsSection.classList.remove('hidden');
        
        if (data.success) {
            successMsg.classList.remove('hidden');
            btnClose.classList.remove('hidden');
            
            let html = '<div class="space-y-2">';
            if (data.results) {
                data.results.forEach(result => {
                    html += `
                        <div class="flex items-center gap-2 text-sm text-green-700 dark:text-green-300">
                            <span class="material-symbols-outlined text-green-500">check_circle</span>
                            <span>${result.script}: ${result.output}</span>
                        </div>
                    `;
                });
            }
            html += '</div>';
            resultsDetailsDiv.innerHTML = html;
        } else {
            errorMsg.classList.remove('hidden');
            errorDetails.textContent = data.error || 'An unknown error occurred';
            btnViewLogs.classList.remove('hidden');
            
            this.logsContent = this.formatLogs(data);
        }
    }
    
    showSuccess(message) {
        const progressSection = document.getElementById('update-progress');
        const resultsSection = document.getElementById('update-results');
        const successMsg = document.getElementById('success-message');
        const successDetails = document.getElementById('success-details');
        const btnClose = document.getElementById('btn-close');
        
        progressSection.classList.add('hidden');
        resultsSection.classList.remove('hidden');
        successMsg.classList.remove('hidden');
        successDetails.textContent = message;
        btnClose.classList.remove('hidden');
    }
    
    showError(message) {
        const progressSection = document.getElementById('update-progress');
        const resultsSection = document.getElementById('update-results');
        const errorMsg = document.getElementById('error-message');
        const errorDetails = document.getElementById('error-details');
        const btnViewLogs = document.getElementById('btn-view-logs');
        
        progressSection.classList.add('hidden');
        resultsSection.classList.remove('hidden');
        errorMsg.classList.remove('hidden');
        errorDetails.textContent = message;
        btnViewLogs.classList.remove('hidden');
    }
    
    formatLogs(data) {
        let logs = '';
        if (data.results) {
            data.results.forEach(result => {
                logs += `\n=== ${result.script} ===\n`;
                logs += `Status: ${result.status}\n`;
                if (result.error) {
                    logs += `Error: ${result.error}\n`;
                    logs += `\nTraceback:\n${result.traceback}\n`;
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

// Initialize update manager
new UpdateManager();