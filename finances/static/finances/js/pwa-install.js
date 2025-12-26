// PWA Install Prompt Manager
// Handles install button visibility and installation process

(function() {
    'use strict';

    let deferredPrompt = null;
    const installContainer = document.getElementById('pwa-install-container');
    const installBtn = document.getElementById('pwa-install-btn');

    if (!installContainer || !installBtn) {
        console.log('[PWA Install] Install button elements not found');
        return;
    }

    // Check if app is already installed
    if (window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone) {
        console.log('[PWA Install] App is already installed');
        return;
    }

    // Detect iOS
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;

    // Listen for beforeinstallprompt event (Android/Desktop)
    window.addEventListener('beforeinstallprompt', (e) => {
        console.log('[PWA Install] beforeinstallprompt event fired');

        // Prevent the default install prompt
        e.preventDefault();

        // Store the event for later use
        deferredPrompt = e;

        // Show the install button
        installContainer.classList.remove('hidden');
    });

    // Handle install button click
    installBtn.addEventListener('click', async () => {
        console.log('[PWA Install] Install button clicked');

        // iOS: Show instructions modal
        if (isIOS) {
            showIOSInstallInstructions();
            return;
        }

        // Android/Desktop: Show native install prompt
        if (!deferredPrompt) {
            console.log('[PWA Install] No deferred prompt available');
            return;
        }

        // Show the install prompt
        deferredPrompt.prompt();

        // Wait for the user to respond
        const { outcome } = await deferredPrompt.userChoice;
        console.log('[PWA Install] User choice:', outcome);

        if (outcome === 'accepted') {
            console.log('[PWA Install] User accepted the install prompt');
        } else {
            console.log('[PWA Install] User dismissed the install prompt');
        }

        // Clear the deferred prompt
        deferredPrompt = null;

        // Hide the install button
        installContainer.classList.add('hidden');
    });

    // Listen for app installed event
    window.addEventListener('appinstalled', () => {
        console.log('[PWA Install] App was installed');

        // Hide the install button
        installContainer.classList.add('hidden');

        // Clear the deferred prompt
        deferredPrompt = null;
    });

    // Show iOS install instructions using existing modal system
    function showIOSInstallInstructions() {
        // Check if modal functions exist
        if (typeof window.showModal !== 'function') {
            // Fallback: alert with i18n support
            const title = window.BASE_I18N?.pwaIosInstructions || 'To install this app on your iPhone/iPad:';
            const step1 = window.BASE_I18N?.pwaIosStep1 || 'Tap the Share button (square with arrow)';
            const step2 = window.BASE_I18N?.pwaIosStep2 || 'Scroll down and tap "Add to Home Screen"';
            const step3 = window.BASE_I18N?.pwaIosStep3 || 'Tap "Add" to install';

            alert(
                `${title}\n\n` +
                `1. ${step1}\n` +
                `2. ${step2}\n` +
                `3. ${step3}`
            );
            return;
        }

        // Use existing modal system
        const title = 'Install on iOS';
        const content = `
            <div class="space-y-4">
                <p class="text-gray-700 dark:text-gray-300">
                    To install SweetMoney on your iPhone or iPad:
                </p>
                <ol class="list-decimal list-inside space-y-2 text-gray-700 dark:text-gray-300">
                    <li>Tap the <strong>Share button</strong>
                        <span class="inline-flex items-center justify-center w-6 h-6 bg-blue-500 text-white rounded text-xs">
                            ⎙
                        </span>
                        at the bottom of your screen
                    </li>
                    <li>Scroll down and tap <strong>"Add to Home Screen"</strong></li>
                    <li>Tap <strong>"Add"</strong> in the top right to install</li>
                </ol>
                <p class="text-sm text-gray-500 dark:text-gray-400 mt-4">
                    The app icon will appear on your home screen
                </p>
            </div>
        `;

        window.showModal(title, content);
    }

    // For iOS: Show install button if not installed
    if (isIOS && !window.navigator.standalone) {
        console.log('[PWA Install] iOS detected, showing install button');
        installContainer.classList.remove('hidden');
    }

})();
