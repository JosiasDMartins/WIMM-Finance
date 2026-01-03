// ============================================
// PERIOD_MODAL.JS - PHASE 3 CSP COMPLIANCE
// ============================================
// Period Change Confirmation Modal Logic
// Version: 20251231-001
// Extracted from period_change_confirmation_modal.html

(function() {
    'use strict';

    const modal = document.getElementById('period-change-modal');
    const checkbox = document.getElementById('modal-confirmation-checkbox');
    const confirmBtn = document.getElementById('modal-confirm-btn');
    const cancelBtn = document.getElementById('modal-cancel-btn');

    // Enable/disable confirm button based on checkbox
    if (checkbox && confirmBtn) {
        checkbox.addEventListener('change', function() {
            confirmBtn.disabled = !this.checked;
        });
    }

    // Cancel button closes modal
    if (cancelBtn && modal) {
        cancelBtn.addEventListener('click', function() {
            closePeriodChangeModal();
        });
    }

    // Close modal function
    window.closePeriodChangeModal = function() {
        if (modal) {
            modal.classList.add('hidden');
            modal.style.display = 'none';

            // Reset checkbox
            if (checkbox) {
                checkbox.checked = false;
            }

            // Disable confirm button
            if (confirmBtn) {
                confirmBtn.disabled = true;
            }
        }
    };

    // Show modal function (called from configurations.html)
    window.showPeriodChangeModal = function(impactData) {
        if (!modal) return;

        console.log('[PERIOD MODAL] Showing modal with impact data:', impactData);

        // Populate modal with data
        document.getElementById('modal-old-period-type').textContent = impactData.old_period_type_label;
        document.getElementById('modal-old-period-dates').textContent = impactData.current_period_label;
        document.getElementById('modal-old-period-days').textContent = impactData.current_period_days;

        document.getElementById('modal-new-period-type').textContent = impactData.new_period_type_label;
        document.getElementById('modal-new-period-dates').textContent = impactData.new_period_label;
        document.getElementById('modal-new-period-days').textContent = impactData.new_period_days;

        document.getElementById('modal-impact-message').textContent = impactData.message;

        // Show/hide adjustment section
        const adjustmentSection = document.getElementById('modal-adjustment-section');
        const adjustmentAction = document.getElementById('modal-action-adjustment');

        if (impactData.adjustment_period) {
            adjustmentSection.style.display = 'table-cell';
            adjustmentAction.classList.remove('hidden');
            document.getElementById('modal-adjustment-dates').textContent = impactData.adjustment_period_label;
            document.getElementById('modal-adjustment-days').textContent = impactData.adjustment_period_days;
        } else {
            adjustmentSection.style.display = 'none';
            adjustmentAction.classList.add('hidden');
        }

        // Show modal
        modal.classList.remove('hidden');
        modal.style.display = 'block';
    };

    // Close modal when clicking outside
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closePeriodChangeModal();
            }
        });
    }

    // ESC key closes modal
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal && !modal.classList.contains('hidden')) {
            closePeriodChangeModal();
        }
    });

    console.log('[PERIOD MODAL] Period change modal initialized');
})();
