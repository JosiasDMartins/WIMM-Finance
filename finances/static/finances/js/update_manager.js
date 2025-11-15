// ============================
// Update Manager - Central controller for app updates
// ============================

class UpdateManager {
    constructor() {
        this.modal = null;
        this.checkAttempts = 0;
        this.maxAttempts = 3;
    }

    init() {
        // Tenta inicializar imediatamente
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setup());
        } else {
            this.setup();
        }
    }

    setup() {
        this.modal = document.getElementById('updateModal');
        
        if (!this.modal) {
            // Se o modal não existir, tenta novamente após 1 segundo (max 3 tentativas)
            this.checkAttempts++;
            if (this.checkAttempts < this.maxAttempts) {
                setTimeout(() => this.setup(), 1000);
            }
            return;
        }

        this.setupEventListeners();
        this.checkForUpdates();
    }

    setupEventListeners() {
        // Botão de fechar modal
        const closeBtn = this.modal?.querySelector('.close');
        if (closeBtn) {
            closeBtn.onclick = () => this.closeModal();
        }

        // Botão de aplicar updates locais
        const applyBtn = document.getElementById('applyLocalUpdates');
        if (applyBtn) {
            applyBtn.onclick = () => this.applyLocalUpdates();
        }

        // Botão de download GitHub
        const downloadBtn = document.getElementById('downloadGithubUpdate');
        if (downloadBtn) {
            downloadBtn.onclick = () => this.downloadGithubUpdate();
        }

        // Botão de skip
        const skipBtn = document.getElementById('skipUpdate');
        if (skipBtn) {
            skipBtn.onclick = () => this.skipUpdate();
        }

        // Botão de criar backup
        const backupBtn = document.getElementById('createBackupBtn');
        if (backupBtn) {
            backupBtn.onclick = () => this.createBackup();
        }

        // Botão de check manual (Settings page)
        const manualCheckBtn = document.getElementById('manualCheckUpdates');
        if (manualCheckBtn) {
            manualCheckBtn.onclick = () => this.manualCheckUpdates();
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

    async checkForUpdates() {
        try {
            const response = await fetch('/check-updates/');
            const data = await response.json();

            if (data.needs_update) {
                this.showUpdateModal(data);
            }
        } catch (error) {
            console.error('Error checking for updates:', error);
        }
    }

    async manualCheckUpdates() {
        const btn = document.getElementById('manualCheckUpdates');
        const originalText = btn?.textContent;
        
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Verificando...';
        }

        try {
            const response = await fetch('/manual-check-updates/');
            const data = await response.json();

            if (data.local_update_available) {
                // Busca detalhes completos da atualização local
                const detailResponse = await fetch('/check-updates/');
                const detailData = await detailResponse.json();
                
                if (detailData.needs_update) {
                    this.showUpdateModal(detailData);
                    return;
                }
            }

            if (data.github_update_available) {
                // Monta dados no formato esperado pelo modal
                const updateData = {
                    needs_update: true,
                    update_type: 'github',
                    current_version: data.current_version,
                    target_version: data.github_version,
                    github_release: data.github_release,
                    requires_container: data.requires_container,
                    can_skip: true
                };
                this.showUpdateModal(updateData);
                return;
            }

            // Nenhuma atualização disponível
            alert('Nenhuma atualização disponível. Você está na versão mais recente!');

        } catch (error) {
            console.error('Error checking for updates:', error);
            alert('Erro ao verificar atualizações. Tente novamente.');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = originalText;
            }
        }
    }

    showUpdateModal(data) {
        if (!this.modal) return;

        const title = this.modal.querySelector('#updateModalTitle');
        const content = this.modal.querySelector('#updateModalContent');
        const localSection = this.modal.querySelector('#localUpdateSection');
        const githubSection = this.modal.querySelector('#githubUpdateSection');
        const skipBtn = document.getElementById('skipUpdate');

        if (data.update_type === 'local') {
            if (title) title.textContent = 'Atualização de Banco de Dados Necessária';
            
            let scriptsHtml = '';
            if (data.has_scripts && data.update_scripts.length > 0) {
                scriptsHtml = '<ul class="update-scripts-list">';
                data.update_scripts.forEach(script => {
                    scriptsHtml += `<li><strong>v${script.version}:</strong> ${script.description}</li>`;
                });
                scriptsHtml += '</ul>';
            }

            if (content) {
                content.innerHTML = `
                    <p>Uma atualização do banco de dados é necessária.</p>
                    <p><strong>Versão Atual:</strong> ${data.current_version}</p>
                    <p><strong>Nova Versão:</strong> ${data.target_version}</p>
                    ${scriptsHtml}
                    <p class="warning-text">⚠️ É altamente recomendado fazer um backup antes de continuar.</p>
                `;
            }

            if (localSection) localSection.style.display = 'block';
            if (githubSection) githubSection.style.display = 'none';
            if (skipBtn) skipBtn.style.display = 'none';

        } else if (data.update_type === 'github') {
            if (title) title.textContent = 'Nova Versão Disponível no GitHub';
            
            if (content) {
                content.innerHTML = `
                    <p>Uma nova versão está disponível no GitHub.</p>
                    <p><strong>Versão Atual:</strong> ${data.current_version}</p>
                    <p><strong>Nova Versão:</strong> ${data.target_version}</p>
                    ${data.github_release.body ? `<div class="release-notes">${data.github_release.body}</div>` : ''}
                    ${data.requires_container ? '<p class="warning-text">⚠️ Esta atualização requer rebuild do container Docker.</p>' : ''}
                `;
            }

            if (localSection) localSection.style.display = 'none';
            if (githubSection) githubSection.style.display = 'block';
            if (skipBtn) skipBtn.style.display = data.can_skip ? 'inline-block' : 'none';
        }

        this.modal.style.display = 'block';
        this.currentUpdateData = data;
    }

    closeModal() {
        if (this.modal) {
            this.modal.style.display = 'none';
        }
    }

    async createBackup() {
        const btn = document.getElementById('createBackupBtn');
        const originalText = btn?.textContent;
        
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Criando backup...';
        }

        try {
            const response = await fetch('/create-backup/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCookie('csrftoken'),
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();

            if (data.success) {
                alert(`Backup criado com sucesso!\n\nArquivo: ${data.filename}`);
                
                if (data.download_url) {
                    window.location.href = data.download_url;
                }
            } else {
                alert('Erro ao criar backup: ' + data.error);
            }
        } catch (error) {
            console.error('Error creating backup:', error);
            alert('Erro ao criar backup. Tente novamente.');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = originalText;
            }
        }
    }

    async applyLocalUpdates() {
        const btn = document.getElementById('applyLocalUpdates');
        const progressDiv = document.getElementById('updateProgress');
        const progressBar = progressDiv?.querySelector('.progress-bar');
        const progressText = progressDiv?.querySelector('.progress-text');

        if (btn) btn.disabled = true;
        if (progressDiv) progressDiv.style.display = 'block';

        try {
            const scripts = this.currentUpdateData?.update_scripts || [];

            const response = await fetch('/apply-local-updates/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCookie('csrftoken'),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ scripts })
            });

            const data = await response.json();

            if (data.success) {
                if (progressBar) progressBar.style.width = '100%';
                if (progressText) progressText.textContent = 'Atualização concluída! Recarregando...';
                
                setTimeout(() => {
                    window.location.reload();
                }, 2000);
            } else {
                alert('Erro durante a atualização:\n' + (data.error || 'Erro desconhecido'));
                if (btn) btn.disabled = false;
                if (progressDiv) progressDiv.style.display = 'none';
            }
        } catch (error) {
            console.error('Error applying updates:', error);
            alert('Erro ao aplicar atualizações. Tente novamente.');
            if (btn) btn.disabled = false;
            if (progressDiv) progressDiv.style.display = 'none';
        }
    }

    async downloadGithubUpdate() {
        const btn = document.getElementById('downloadGithubUpdate');
        const originalText = btn?.textContent;

        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Baixando...';
        }

        try {
            const response = await fetch('/download-github-update/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCookie('csrftoken'),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    zipball_url: this.currentUpdateData.github_release.zipball_url,
                    target_version: this.currentUpdateData.target_version
                })
            });

            const data = await response.json();

            if (data.success) {
                alert('Atualização baixada com sucesso! A página será recarregada.');
                window.location.reload();
            } else {
                alert('Erro ao baixar atualização: ' + data.error);
            }
        } catch (error) {
            console.error('Error downloading update:', error);
            alert('Erro ao baixar atualização. Tente novamente.');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = originalText;
            }
        }
    }

    async skipUpdate() {
        try {
            const response = await fetch('/skip-updates/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCookie('csrftoken'),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    update_type: this.currentUpdateData.update_type
                })
            });

            const data = await response.json();

            if (data.success) {
                this.closeModal();
            } else {
                alert('Erro ao pular atualização: ' + data.error);
            }
        } catch (error) {
            console.error('Error skipping update:', error);
            alert('Erro ao pular atualização.');
        }
    }
}

// Inicializa o UpdateManager globalmente
const updateManager = new UpdateManager();
updateManager.init();
