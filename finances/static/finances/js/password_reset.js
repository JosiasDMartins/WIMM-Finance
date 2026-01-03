// ============================================
// PASSWORD_RESET.JS - PHASE 3 CSP COMPLIANCE
// ============================================
// Password reset confirm and verify logic
// Version: 20251231-001
// Extracted from: password_reset_confirm.html and password_reset_verify.html

(function() {
    'use strict';

    // ============================================
    // PASSWORD RESET CONFIRM (Set New Password)
    // ============================================

    // Toggle password visibility
    function togglePasswordVisibility(inputId, button) {
        const input = document.getElementById(inputId);
        const icon = button.querySelector('.material-symbols-outlined');

        if (!input || !icon) return;

        if (input.type === 'password') {
            input.type = 'text';
            icon.textContent = 'visibility_off';
        } else {
            input.type = 'password';
            icon.textContent = 'visibility';
        }
    }

    // Attach toggle password handlers
    document.querySelectorAll('[data-action="toggle-password"]').forEach(button => {
        button.addEventListener('click', function() {
            const targetId = this.dataset.target;
            togglePasswordVisibility(targetId, this);
        });
    });

    // Password strength checker
    const newPasswordInput = document.getElementById('new_password');
    const strengthIndicator = document.getElementById('password-strength');
    const strengthBar = document.getElementById('strength-bar');
    const strengthText = document.getElementById('strength-text');

    if (newPasswordInput && strengthIndicator && strengthBar && strengthText) {
        const config = document.getElementById('password-reset-config');
        const i18n = {
            weak: config?.dataset.i18nWeak || 'Weak',
            fair: config?.dataset.i18nFair || 'Fair',
            strong: config?.dataset.i18nStrong || 'Strong'
        };

        newPasswordInput.addEventListener('input', function() {
            const password = this.value;

            if (password.length === 0) {
                strengthIndicator.classList.add('hidden');
                return;
            }

            strengthIndicator.classList.remove('hidden');

            // Calculate strength
            let strength = 0;
            if (password.length >= 8) strength += 25;
            if (password.length >= 12) strength += 25;
            if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength += 25;
            if (/\d/.test(password)) strength += 15;
            if (/[^a-zA-Z0-9]/.test(password)) strength += 10;

            // Update bar
            strengthBar.style.width = strength + '%';

            // Update color and text
            if (strength < 40) {
                strengthBar.className = 'h-2 rounded-full transition-all duration-300 bg-red-500';
                strengthText.textContent = i18n.weak;
                strengthText.className = 'text-xs font-semibold text-red-500';
            } else if (strength < 70) {
                strengthBar.className = 'h-2 rounded-full transition-all duration-300 bg-yellow-500';
                strengthText.textContent = i18n.fair;
                strengthText.className = 'text-xs font-semibold text-yellow-500';
            } else {
                strengthBar.className = 'h-2 rounded-full transition-all duration-300 bg-green-500';
                strengthText.textContent = i18n.strong;
                strengthText.className = 'text-xs font-semibold text-green-500';
            }
        });
    }

    // Form validation for password reset
    const passwordResetForm = document.getElementById('password-reset-form');
    if (passwordResetForm) {
        const config = document.getElementById('password-reset-config');
        const i18n = {
            passwordsDoNotMatch: config?.dataset.i18nPasswordsDoNotMatch || 'Passwords do not match. Please try again.',
            passwordTooShort: config?.dataset.i18nPasswordTooShort || 'Password must be at least 8 characters long.'
        };

        passwordResetForm.addEventListener('submit', async function(e) {
            const newPassword = document.getElementById('new_password')?.value;
            const confirmPassword = document.getElementById('confirm_password')?.value;

            if (newPassword !== confirmPassword) {
                e.preventDefault();
                if (window.GenericModal && window.GenericModal.alert) {
                    await window.GenericModal.alert(i18n.passwordsDoNotMatch, 'Error');
                } else {
                    alert(i18n.passwordsDoNotMatch);
                }
                return false;
            }

            if (newPassword && newPassword.length < 8) {
                e.preventDefault();
                if (window.GenericModal && window.GenericModal.alert) {
                    await window.GenericModal.alert(i18n.passwordTooShort, 'Error');
                } else {
                    alert(i18n.passwordTooShort);
                }
                return false;
            }
        });
    }

    // ============================================
    // PASSWORD RESET VERIFY (Enter Code)
    // ============================================

    // Auto-format the code input (add spacing)
    const codeInput = document.getElementById('code');
    if (codeInput) {
        codeInput.addEventListener('input', function(e) {
            // Remove any non-digit characters
            this.value = this.value.replace(/\D/g, '');
            // Limit to 5 digits
            if (this.value.length > 5) {
                this.value = this.value.slice(0, 5);
            }
        });
    }

    console.log('[PASSWORD_RESET] Password reset utilities initialized');
})();
