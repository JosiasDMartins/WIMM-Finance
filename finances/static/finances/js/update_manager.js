// finances/static/finances/js/update_manager.js
class UpdateManager {
    constructor() {
        this.updateData = null;
        this.init();
    }
    
    init() {
        // Check immediately if DOM is already loaded
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                this.checkForUpdates();
                this.setupEventListeners();
            });
        } else {
            // DOM already loaded, run immediately
            this.checkForUpdates();
            this.setupEventListeners();
        }
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
        
        if (data.has_scripts) {
            updateDesc.textContent = 'Local updates are available and must be applied before continuing.';
            scriptsInfo.classList.remove('hidden');
            scriptsList.innerHTML = '';
            data.update_scripts.forEach(script => {
                const li = document.createElement('li');
                li.textContent = `v${script.version}: ${script.description}`;
                scriptsList.appendChild(li);
            });
        } else {
            updateDesc.textContent = 'System files have been updated. Database migrations will be applied.';
        }
        
        // ALWAYS show apply button for local updates
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
        
        updateDesc.textContent = 'A new version is available from GitHub!';
        
        // Show GitHub info
        githubInfo.classList.remove('hidden');
        releaseName.textContent = data.github_release.name;
        releaseNotes.innerHTML = this.formatMarkdown(data.github_release.body);
        releaseDate.textContent = new Date(data.github_release.published_at).toLocaleDateString();
        
        // Show container warning if needed
        if (data.requires_container) {
            containerWarning.classList.remove('hidden');
            btnInstall.classList.add('hidden');
        } else {
            btnInstall.classList.remove('hidden');
            backupSection.classList.remove('hidden');
        }
        
        btnSkip.classList.remove('hidden');
        btnViewRelease.classList.remove('hidden');
        btnViewRelease.onclick = () => window.open(data.github_release.html_url, '_blank');
    }
    
    formatMarkdown(text) {
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
        progressTitle.textContent = 'Applying Updates...';
        
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
                    scripts: this.updateData.update_scripts || []
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
        progressTitle.textContent = 'Installing Update from GitHub...';
        
        try {
            progressBar.style.width = '10%';
            progressText.textContent = 'Downloading files...';
            
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
            progressText.textContent = 'Files updated successfully!';
            
            const data = await response.json();
            
            if (data.success) {
                // Show success message and reload
                this.showSuccess(data.message + ' - Reloading to apply migrations...');
                setTimeout(() => {
                    location.reload();
                }, 2000);
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
                // Download the backup file
                const downloadLink = document.createElement('a');
                downloadLink.href = `/download-backup/?filename=${data.filename}`;
                downloadLink.download = data.filename;
                document.body.appendChild(downloadLink);
                downloadLink.click();
                document.body.removeChild(downloadLink);
                
                btn.innerHTML = '<span class="material-symbols-outlined">check_circle</span> Backup Downloaded';
                btn.classList.remove('bg-amber-600', 'hover:bg-amber-700');
                btn.classList.add('bg-green-600');
                
                // Enable the update button after 1 second
                setTimeout(() => {
                    document.getElementById('backup-confirmed').checked = true;
                    document.getElementById('btn-install-github').disabled = false;
                }, 1000);
            } else {
                throw new Error(data.error);
            }
        } catch (error) {
            btn.innerHTML = originalText;
            btn.disabled = false;
            alert('Failed to create backup: ' + error.message);
        }
    }
    
    async skipUpdate() {
        if (!confirm('Are you sure you want to skip this update?')) {
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
                location.reload();
            } else {
                alert('Error: ' + data.error);
            }
        } catch (error) {
            alert('Network error: ' + error.message);
        }
    }
    
    showResults(data) {
        const mainContent = document.getElementById('main-content');
        const progressSection = document.getElementById('update-progress');
        const modalIcon = document.getElementById('modal-icon');
        const modalTitle = document.getElementById('modal-title');
        const btnClose = document.getElementById('btn-close');
        const btnViewLogs = document.getElementById('btn-view-logs');
        
        progressSection.classList.add('hidden');
        
        if (data.success) {
            modalIcon.className = 'material-symbols-outlined text-4xl text-green-500';
            modalIcon.textContent = 'check_circle';
            modalTitle.textContent = 'Update Complete!';
            
            mainContent.innerHTML = `
                <div class="bg-green-50 dark:bg-green-900/20 border-l-4 border-green-500 p-4 mb-4">
                    <p class="text-green-800 dark:text-green-300 font-medium">
                        System successfully updated to version ${data.new_version}
                    </p>
                </div>
                <div class="space-y-2">
                    <p class="font-semibold text-gray-900 dark:text-gray-200">Applied Updates:</p>
                    <ul class="list-disc list-inside space-y-1 text-sm text-gray-700 dark:text-gray-400">
                        ${data.results.map(r => `
                            <li>
                                ${r.script}: 
                                <span class="font-medium ${r.status === 'success' ? 'text-green-600' : 'text-red-600'}">
                                    ${r.status}
                                </span>
                            </li>
                        `).join('')}
                    </ul>
                </div>
            `;
            
            this.logsData = data.results;
            btnViewLogs.classList.remove('hidden');
            btnClose.classList.remove('hidden');
        } else {
            this.showError('Update failed: ' + data.error);
        }
    }
    
    showSuccess(message) {
        const mainContent = document.getElementById('main-content');
        const progressSection = document.getElementById('update-progress');
        const modalIcon = document.getElementById('modal-icon');
        const modalTitle = document.getElementById('modal-title');
        
        progressSection.classList.add('hidden');
        modalIcon.className = 'material-symbols-outlined text-4xl text-green-500';
        modalIcon.textContent = 'check_circle';
        modalTitle.textContent = 'Success!';
        
        mainContent.innerHTML = `
            <div class="bg-green-50 dark:bg-green-900/20 border-l-4 border-green-500 p-4">
                <p class="text-green-800 dark:text-green-300">${message}</p>
            </div>
        `;
    }
    
    showError(message) {
        const mainContent = document.getElementById('main-content');
        const progressSection = document.getElementById('update-progress');
        const modalIcon = document.getElementById('modal-icon');
        const modalTitle = document.getElementById('modal-title');
        const btnClose = document.getElementById('btn-close');
        
        progressSection.classList.add('hidden');
        modalIcon.className = 'material-symbols-outlined text-4xl text-red-500';
        modalIcon.textContent = 'error';
        modalTitle.textContent = 'Update Failed';
        
        mainContent.innerHTML = `
            <div class="bg-red-50 dark:bg-red-900/20 border-l-4 border-red-500 p-4">
                <p class="text-red-800 dark:text-red-300 font-medium">${message}</p>
            </div>
        `;
        
        btnClose.classList.remove('hidden');
    }
    
    showLogs() {
        if (!this.logsData) return;
        
        const logsModal = document.getElementById('logs-modal');
        const logsContent = document.getElementById('logs-content');
        
        let logsText = '';
        this.logsData.forEach(result => {
            logsText += `\n=== ${result.script} (v${result.version}) ===\n`;
            logsText += `Status: ${result.status}\n`;
            if (result.output) {
                logsText += `Output:\n${result.output}\n`;
            }
            if (result.error) {
                logsText += `Error:\n${result.error}\n`;
            }
            if (result.traceback) {
                logsText += `Traceback:\n${result.traceback}\n`;
            }
            logsText += '\n';
        });
        
        logsContent.textContent = logsText;
        logsModal.classList.remove('hidden');
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

// Initialize UpdateManager
const updateManager = new UpdateManager();
