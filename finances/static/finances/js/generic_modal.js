/**
 * Generic Modal System
 * PHASE 3 CSP Compliance - Centralized modal management
 * Version: 20260101-001
 *
 * Provides a Promise-based modal system for alerts and confirmations
 */

'use strict';

// Load i18n from data attributes (loaded from base.html or base_simple.html)
// window.MODAL_I18N should already be set by base.js
// If not set, provide fallback defaults
if (typeof window.MODAL_I18N === 'undefined') {
    const config = document.getElementById('base-config');
    if (config) {
        window.MODAL_I18N = {
            notification: config.dataset.i18nModalNotification || 'Notification',
            warning: config.dataset.i18nModalWarning || 'Warning',
            error: config.dataset.i18nModalError || 'Error',
            success: config.dataset.i18nModalSuccess || 'Success',
            confirm: config.dataset.i18nModalConfirm || 'Confirm Action',
            ok: config.dataset.i18nModalOk || 'OK',
            cancel: config.dataset.i18nModalCancel || 'Cancel',
            continue: config.dataset.i18nModalContinue || 'Continue',
            yes: config.dataset.i18nModalYes || 'Yes',
            no: config.dataset.i18nModalNo || 'No',
            close: config.dataset.i18nModalClose || 'Close'
        };
    } else {
        // Ultimate fallback
        window.MODAL_I18N = {
            notification: 'Notification',
            warning: 'Warning',
            error: 'Error',
            success: 'Success',
            confirm: 'Confirm Action',
            ok: 'OK',
            cancel: 'Cancel',
            continue: 'Continue',
            yes: 'Yes',
            no: 'No',
            close: 'Close'
        };
    }
}

// Generic Modal Manager
window.GenericModal = {
    show: function(options) {
        const modal = document.getElementById('generic-modal');
        if (!modal) {
            console.error('[GenericModal] Modal element not found!');
            return;
        }

        const title = document.getElementById('modal-title');
        const message = document.getElementById('modal-message');
        const buttonsContainer = document.getElementById('modal-buttons');
        const iconContainer = document.getElementById('modal-icon-container');
        const icon = document.getElementById('modal-icon');

        if (options.title) {
            title.textContent = options.title;
        }

        if (options.message) {
            message.innerHTML = options.message;
        }

        const type = options.type || 'info';
        iconContainer.className = 'mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full sm:mx-0 sm:h-10 sm:w-10';

        if (type === 'warning') {
            iconContainer.classList.add('bg-amber-100', 'dark:bg-amber-900/20');
            icon.classList.add('text-amber-600', 'dark:text-amber-500');
            icon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />';
        } else if (type === 'error') {
            iconContainer.classList.add('bg-red-100', 'dark:bg-red-900/20');
            icon.classList.add('text-red-600', 'dark:text-red-500');
            icon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />';
        } else if (type === 'success') {
            iconContainer.classList.add('bg-green-100', 'dark:bg-green-900/20');
            icon.classList.add('text-green-600', 'dark:text-green-500');
            icon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />';
        } else {
            iconContainer.classList.add('bg-blue-100', 'dark:bg-blue-900/20');
            icon.classList.add('text-blue-600', 'dark:text-blue-500');
            icon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />';
        }

        buttonsContainer.innerHTML = '';
        const buttons = options.buttons || [
            { text: window.MODAL_I18N.ok, primary: true, onClick: () => window.GenericModal.hide() }
        ];

        buttons.forEach(btn => {
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = btn.text;

            if (btn.primary) {
                button.className = 'inline-flex w-full justify-center rounded-lg px-4 py-2 text-sm font-semibold text-white shadow-sm bg-green-600 hover:bg-green-700 sm:w-auto';
            } else {
                button.className = 'inline-flex w-full justify-center rounded-lg px-4 py-2 text-sm font-semibold shadow-sm ring-1 ring-inset bg-white hover:bg-gray-50 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-900 dark:text-white ring-gray-300 dark:ring-gray-600 sm:w-auto';
            }

            button.addEventListener('click', () => {
                if (btn.onClick && typeof btn.onClick === 'function') {
                    btn.onClick();
                }
                window.GenericModal.hide();
            });

            buttonsContainer.appendChild(button);
        });

        modal.classList.remove('hidden');
    },

    hide: function() {
        const modal = document.getElementById('generic-modal');
        if (modal) {
            modal.classList.add('hidden');
        }
    },

    alert: function(message, title, onClose) {
        this.show({
            type: 'info',
            title: title || window.MODAL_I18N.notification,
            message: message,
            buttons: [
                { text: window.MODAL_I18N.ok, primary: true, onClick: onClose }
            ]
        });
    },

    confirm: function(message, title) {
        return new Promise((resolve) => {
            this.show({
                type: 'warning',
                title: title || window.MODAL_I18N.confirm,
                message: message,
                buttons: [
                    { text: window.MODAL_I18N.cancel, primary: false, onClick: () => resolve(false) },
                    { text: window.MODAL_I18N.continue, primary: true, onClick: () => resolve(true) }
                ]
            });
        });
    }
};

console.log('[GenericModal] System loaded successfully');
console.log('[GenericModal] Available methods:', Object.keys(window.GenericModal));
