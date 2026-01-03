// ============================================
// LOGGED_OUT.JS - PHASE 3 CSP COMPLIANCE
// ============================================
// Countdown and redirect after logout
// Version: 20251231-001
// Extracted from: logged_out.html

(function() {
    'use strict';

    let countdown = 3;
    const countdownElement = document.getElementById('countdown');

    if (!countdownElement) {
        console.warn('[LOGGED_OUT] Countdown element not found');
        return;
    }

    const timer = setInterval(() => {
        countdown--;
        countdownElement.textContent = countdown;

        if (countdown <= 0) {
            clearInterval(timer);
            window.location.href = "/login/";
        }
    }, 1000);

    console.log('[LOGGED_OUT] Countdown initialized');
})();
