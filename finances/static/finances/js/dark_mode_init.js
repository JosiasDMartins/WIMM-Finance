/**
 * dark_mode_init.js - Dark mode initialization to prevent FOUC
 * CRITICAL: This script MUST run immediately, before any rendering
 * Version: 20251230-001
 */

// Set initial dark mode state to prevent FOUC
(function () {
    const htmlElement = document.documentElement;
    htmlElement.classList.remove('light');
    const saved = localStorage.getItem('theme');
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    const initial = saved ? saved : (prefersDark ? 'dark' : 'light');
    if (initial === 'dark') {
        htmlElement.classList.add('dark');
    } else {
        htmlElement.classList.remove('dark');
    }
})();
