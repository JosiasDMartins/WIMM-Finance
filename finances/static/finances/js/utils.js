/**
 * utils.js - Common Utility Functions
 *
 * Centralized utility functions used across multiple templates
 * to avoid code duplication and maintain consistency.
 *
 * Version: 1.0.0
 * Created: 2025-12-31
 */

(function() {
    'use strict';

    // ========== COOKIE MANAGEMENT ==========

    /**
     * Get cookie value by name
     * @param {string} name - Cookie name
     * @returns {string|null} Cookie value or null if not found
     */
    function getCookie(name) {
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

    // ========== MONEY/CURRENCY UTILITIES ==========

    /**
     * Get raw numeric value from masked money input
     * Removes thousand separators and converts decimal separator to dot
     * @param {string} maskedValue - Formatted money value
     * @param {string} thousandSeparator - Thousand separator character (default: '.')
     * @param {string} decimalSeparator - Decimal separator character (default: ',')
     * @returns {string} Raw numeric value with dot as decimal separator
     */
    function getRawValue(maskedValue, thousandSeparator = '.', decimalSeparator = ',') {
        if (!maskedValue || maskedValue === '') return '0';

        // Escape special regex characters in the separator
        const escapedSeparator = thousandSeparator.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        let value = maskedValue.replace(new RegExp(escapedSeparator, 'g'), '');
        value = value.replace(decimalSeparator, '.');
        return value;
    }

    /**
     * Apply money mask to input field
     * Formats value as currency with thousand and decimal separators
     * @param {Event} event - Input event
     * @param {string} thousandSeparator - Thousand separator (default: '.')
     * @param {string} decimalSeparator - Decimal separator (default: ',')
     */
    function applyMoneyMask(event, thousandSeparator = '.', decimalSeparator = ',') {
        const input = event.target;
        const originalCursorPos = input.selectionStart;
        const originalValue = input.value;

        let value = input.value;

        // Remove all non-digit characters
        value = value.replace(/\D/g, '');

        if (value === '') {
            input.value = '0' + decimalSeparator + '00';
            setTimeout(function() {
                input.setSelectionRange(input.value.length, input.value.length);
            }, 0);
            return;
        }

        // Convert to cents
        let cents = parseInt(value, 10);
        let integerPart = Math.floor(cents / 100).toString();
        let decimalPart = (cents % 100).toString().padStart(2, '0');

        // Add thousand separators
        integerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, thousandSeparator);

        input.value = integerPart + decimalSeparator + decimalPart;

        // Restore cursor position
        const newLength = input.value.length;
        const oldLength = originalValue.length;
        let newCursorPos = originalCursorPos + (newLength - oldLength);
        if (newCursorPos < 0) { newCursorPos = 0; }
        input.setSelectionRange(newCursorPos, newCursorPos);
    }

    /**
     * Format amount for input field
     * @param {number|string} amount - Amount to format
     * @param {string} thousandSeparator - Thousand separator (default: '.')
     * @param {string} decimalSeparator - Decimal separator (default: ',')
     * @returns {string} Formatted amount
     */
    function formatAmountForInput(amount, thousandSeparator = '.', decimalSeparator = ',') {
        if (amount === null || amount === undefined || amount === '') {
            return '0' + decimalSeparator + '00';
        }

        let num = parseFloat(amount);
        if (isNaN(num)) {
            return '0' + decimalSeparator + '00';
        }

        let cents = Math.round(num * 100);
        let integerPart = Math.floor(cents / 100).toString();
        let decimalPart = (cents % 100).toString().padStart(2, '0');

        // Add thousand separators
        integerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, thousandSeparator);

        return integerPart + decimalSeparator + decimalPart;
    }

    /**
     * Format currency for display
     * @param {number|string} amount - Amount to format
     * @param {string} currencySymbol - Currency symbol (default: 'R$')
     * @param {string} thousandSeparator - Thousand separator (default: '.')
     * @param {string} decimalSeparator - Decimal separator (default: ',')
     * @returns {string} Formatted currency string
     */
    function formatCurrency(amount, currencySymbol = 'R$', thousandSeparator = '.', decimalSeparator = ',') {
        const num = parseFloat(amount);
        if (isNaN(num)) return amount;

        const cents = Math.round(num * 100);
        let integerPart = Math.floor(cents / 100).toString();
        let decimalPart = (cents % 100).toString().padStart(2, '0');

        // Add thousand separators
        integerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, thousandSeparator);

        return currencySymbol + ' ' + integerPart + decimalSeparator + decimalPart;
    }

    // ========== INPUT FOCUS/CURSOR UTILITIES ==========

    /**
     * Initialize cursor positioning for amount input fields
     * Positions cursor to the right on first focus, allows normal editing on subsequent focuses
     * @param {string} selector - CSS selector for input fields (default: 'input[data-field="amount"]')
     */
    function initializeCursorPositioning(selector = 'input[data-field="amount"]') {
        // Cursor positioned to the right only on first click/focus
        document.addEventListener('focus', function(event) {
            if (event.target.matches(selector)) {
                if (!event.target.hasAttribute('data-first-focus-done')) {
                    event.target.setAttribute('data-first-focus-done', 'true');
                    setTimeout(function() {
                        event.target.setSelectionRange(event.target.value.length, event.target.value.length);
                    }, 0);
                }
            }
        }, true);

        // Reset flags when field loses focus
        document.addEventListener('blur', function(event) {
            if (event.target.matches(selector)) {
                event.target.removeAttribute('data-first-focus-done');
            }
        }, true);
    }

    // ========== UI FEEDBACK ==========

    /**
     * Show success message notification
     * @param {string} message - Message to display
     * @param {number} duration - Duration in milliseconds (default: 3000)
     */
    function showSuccessMessage(message, duration = 3000) {
        // Check if there's a notification system available
        if (window.NotificationManager && typeof window.NotificationManager.show === 'function') {
            window.NotificationManager.show(message, 'success', duration);
            return;
        }

        // Fallback: Create simple toast notification
        const toast = document.createElement('div');
        toast.className = 'fixed top-4 right-4 bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 transition-opacity duration-300';
        toast.textContent = message;
        toast.style.opacity = '0';

        document.body.appendChild(toast);

        // Fade in
        setTimeout(() => {
            toast.style.opacity = '1';
        }, 10);

        // Fade out and remove
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => {
                document.body.removeChild(toast);
            }, 300);
        }, duration);
    }

    /**
     * Show error message notification
     * @param {string} message - Message to display
     * @param {number} duration - Duration in milliseconds (default: 5000)
     */
    function showErrorMessage(message, duration = 5000) {
        // Check if there's a notification system available
        if (window.NotificationManager && typeof window.NotificationManager.show === 'function') {
            window.NotificationManager.show(message, 'error', duration);
            return;
        }

        // Fallback: Create simple toast notification
        const toast = document.createElement('div');
        toast.className = 'fixed top-4 right-4 bg-red-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 transition-opacity duration-300';
        toast.textContent = message;
        toast.style.opacity = '0';

        document.body.appendChild(toast);

        // Fade in
        setTimeout(() => {
            toast.style.opacity = '1';
        }, 10);

        // Fade out and remove
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => {
                document.body.removeChild(toast);
            }, 300);
        }, duration);
    }

    // ========== EXPORT TO WINDOW ==========

    // Export all utility functions to window object
    window.FinancesUtils = {
        // Cookie management
        getCookie: getCookie,

        // Money/Currency utilities
        getRawValue: getRawValue,
        applyMoneyMask: applyMoneyMask,
        formatAmountForInput: formatAmountForInput,
        formatCurrency: formatCurrency,

        // Input focus/cursor utilities
        initializeCursorPositioning: initializeCursorPositioning,

        // UI feedback
        showSuccessMessage: showSuccessMessage,
        showErrorMessage: showErrorMessage
    };

    // Also export individual functions for backward compatibility
    window.getCookie = getCookie;
    window.getRawValue = getRawValue;
    window.applyMoneyMask = applyMoneyMask;
    window.formatAmountForInput = formatAmountForInput;
    window.formatCurrency = formatCurrency;
    window.initializeCursorPositioning = initializeCursorPositioning;
    window.showSuccessMessage = showSuccessMessage;
    window.showErrorMessage = showErrorMessage;

    console.log('[FinancesUtils] Utility functions loaded successfully');

})();
