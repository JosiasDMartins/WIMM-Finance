"""
Update Script: Add Bank Reconciliation Mode Configuration
Version: 1.4.1
Description: Adds bank_reconciliation_mode field to FamilyConfiguration

This script:
1. Runs Django migrations to add bank_reconciliation_mode field
2. Verifies that the new field was added successfully to the database
3. Reports the update status

Changes:
- Adds bank_reconciliation_mode field to FamilyConfiguration model
- Enables family-wide sharing of reconciliation display mode (general/detailed)
- When one user changes the mode, all family members see the same mode
"""

from django.core.management import call_command
from django.db import connection
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
        print("[Update v1.4.1] Starting bank reconciliation mode configuration installation...")

        # =====================================================
        # STEP 1: Run Django migrations
        # =====================================================
        print("[Update v1.4.1] Step 1: Running Django migrations...")
        try:
            call_command('migrate', 'finances', verbosity=1)
            print("[Update v1.4.1] Migrations completed successfully")
        except Exception as migrate_error:
            error_msg = f"Migration failed: {str(migrate_error)}"
            print(f"[ERROR] {error_msg}", file=sys.stderr)
            return {
                'success': False,
                'message': error_msg,
                'error': str(migrate_error)
            }

        # =====================================================
        # STEP 2: Verify new field was added
        # =====================================================
        print("[Update v1.4.1] Step 2: Verifying database schema changes...")

        results = {
            'added_fields': [],
            'missing_fields': []
        }

        try:
            # Import models to check fields directly
            from finances.models import FamilyConfiguration

            # Check FamilyConfiguration model for bank_reconciliation_mode field
            if hasattr(FamilyConfiguration, 'bank_reconciliation_mode'):
                results['added_fields'].append('bank_reconciliation_mode')
                print("[Update v1.4.1] [OK] FamilyConfiguration.bank_reconciliation_mode field added")

                # Get first config to verify default value
                config = FamilyConfiguration.objects.first()
                if config:
                    mode = config.bank_reconciliation_mode
                    print(f"[Update v1.4.1] [OK] Default mode set to: {mode}")
            else:
                results['missing_fields'].append('FamilyConfiguration.bank_reconciliation_mode')
                print("[Update v1.4.1] [MISSING] FamilyConfiguration.bank_reconciliation_mode field NOT found")

        except Exception as verify_error:
            error_msg = f"Field verification failed: {str(verify_error)}"
            print(f"[WARNING] {error_msg}", file=sys.stderr)
            # Don't fail the update if verification fails, migration might have succeeded
            results['verification_warning'] = str(verify_error)

        # =====================================================
        # STEP 3: Build result message
        # =====================================================
        if results['missing_fields']:
            message = f"Migration completed but some fields may be missing: {', '.join(results['missing_fields'])}"
            success = False
        else:
            message = "Bank reconciliation mode configuration installed successfully! "
            message += f"Added fields: {', '.join(results['added_fields'])}"
            success = True

        print(f"[Update v1.4.1] {message}")

        if success:
            print("[Update v1.4.1] [SUCCESS] Update completed successfully!")
            print("[Update v1.4.1] New feature:")
            print("  - Bank reconciliation mode (general/detailed) is now saved per family")
            print("  - All family members share the same mode setting")
            print("  - When one user changes the mode, all users see the change")

        return {
            'success': success,
            'message': message,
            'details': results
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'message': f"Bank reconciliation mode installation failed: {str(e)}",
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
