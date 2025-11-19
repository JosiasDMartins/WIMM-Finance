"""
Update Script: Add Bank Reconciliation Tolerance Configuration
Version: 1.0.0-beta
Description: Adds configurable tolerance percentage for bank reconciliation warnings

This script:
1. Runs Django migrations to add the bank_reconciliation_tolerance field
2. Sets default 5% tolerance for all existing families
"""

from decimal import Decimal
from django.db import transaction
from django.core.management import call_command
import sys


def run():
    """
    Main execution function.
    Must return a dict with:
        - success: bool
        - message: str
        - details: dict (optional)
    """
    try:
        print("[Update v1.0.0-beta] Starting bank reconciliation tolerance update...")

        # =====================================================
        # STEP 1: Run Django migrations
        # =====================================================
        print("[Update v1.0.0-beta] Step 1: Running Django migrations...")
        try:
            call_command('migrate', verbosity=1)
            print("[Update v1.0.0-beta] Migrations completed successfully")
        except Exception as migrate_error:
            error_msg = f"Migration failed: {str(migrate_error)}"
            print(f"[ERROR] {error_msg}", file=sys.stderr)
            return {
                'success': False,
                'message': error_msg,
                'error': str(migrate_error)
            }

        # =====================================================
        # STEP 2: Set default tolerance for existing families
        # =====================================================
        print("[Update v1.0.0-beta] Step 2: Setting default tolerance...")

        # Import models here to avoid circular imports
        from finances.models import FamilyConfiguration

        results = {
            'total_families': 0,
            'updated_families': 0,
            'already_configured': 0
        }

        with transaction.atomic():
            all_configs = FamilyConfiguration.objects.all()
            results['total_families'] = all_configs.count()

            for config in all_configs:
                # Check if tolerance is None or 0 (invalid values)
                if config.bank_reconciliation_tolerance is None or config.bank_reconciliation_tolerance == 0:
                    config.bank_reconciliation_tolerance = Decimal('5.00')
                    config.save(update_fields=['bank_reconciliation_tolerance'])
                    results['updated_families'] += 1
                    print(f"[Update v1.0.0-beta] Set 5% tolerance for family: {config.family.name}")
                else:
                    results['already_configured'] += 1

        # =====================================================
        # STEP 3: Verify the update
        # =====================================================
        print("[Update v1.0.0-beta] Step 3: Verifying update...")

        configs_without_tolerance = FamilyConfiguration.objects.filter(
            bank_reconciliation_tolerance__isnull=True
        ).count()

        if configs_without_tolerance > 0:
            error_msg = f"Verification failed: {configs_without_tolerance} families still without tolerance"
            print(f"[ERROR] {error_msg}", file=sys.stderr)
            return {
                'success': False,
                'message': error_msg,
                'details': results
            }

        # Build success message
        if results['updated_families'] == 0:
            message = f"All {results['total_families']} familie(s) already had tolerance configured"
        else:
            message = f"Successfully configured tolerance for {results['updated_families']} of {results['total_families']} familie(s)"

        print(f"[Update v1.0.0-beta] {message}")
        print("[Update v1.0.0-beta] Update completed successfully!")

        return {
            'success': True,
            'message': message,
            'details': results
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'message': f"Bank reconciliation tolerance update failed: {str(e)}",
            'error': str(e)
        }


# For testing purposes
if __name__ == "__main__":
    import os
    import django

    # Setup Django environment
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wimm_project.settings')
    django.setup()

    # Run the update
    result = run()
    print(f"\nSuccess: {result['success']}")
    print(f"Message: {result['message']}")
    if 'details' in result:
        print(f"Details: {result['details']}")
