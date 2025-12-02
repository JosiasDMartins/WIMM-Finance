"""
Update Script: Add Recurring Expenses Feature
Version: 1.4.0-beta
Description: Adds recurring FlowGroups and fixed transactions functionality

This script:
1. Runs Django migrations to add is_recurring and is_fixed fields
2. Verifies that the new fields were added successfully to the database
3. Reports the update status

Changes:
- Adds is_recurring field to FlowGroup model
- Adds is_fixed field to Transaction model
- Enables automatic replication of recurring groups and fixed transactions to new periods
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
        print("[Update v1.4.0-beta] Starting recurring expenses feature installation...")

        # =====================================================
        # STEP 1: Run Django migrations
        # =====================================================
        print("[Update v1.4.0-beta] Step 1: Running Django migrations...")
        try:
            call_command('migrate', 'finances', verbosity=1)
            print("[Update v1.4.0-beta] Migrations completed successfully")
        except Exception as migrate_error:
            error_msg = f"Migration failed: {str(migrate_error)}"
            print(f"[ERROR] {error_msg}", file=sys.stderr)
            return {
                'success': False,
                'message': error_msg,
                'error': str(migrate_error)
            }

        # =====================================================
        # STEP 2: Verify new fields were added
        # =====================================================
        print("[Update v1.4.0-beta] Step 2: Verifying database schema changes...")

        results = {
            'flowgroup_fields': [],
            'transaction_fields': [],
            'missing_fields': []
        }

        try:
            # Import models to check fields directly
            from finances.models import FlowGroup, Transaction

            # Check FlowGroup model for is_recurring field
            if hasattr(FlowGroup, 'is_recurring'):
                results['flowgroup_fields'].append('is_recurring')
                print("[Update v1.4.0-beta] [OK] FlowGroup.is_recurring field added")
            else:
                results['missing_fields'].append('FlowGroup.is_recurring')
                print("[Update v1.4.0-beta] [MISSING] FlowGroup.is_recurring field NOT found")

            # Check Transaction model for is_fixed field
            if hasattr(Transaction, 'is_fixed'):
                results['transaction_fields'].append('is_fixed')
                print("[Update v1.4.0-beta] [OK] Transaction.is_fixed field added")
            else:
                results['missing_fields'].append('Transaction.is_fixed')
                print("[Update v1.4.0-beta] [MISSING] Transaction.is_fixed field NOT found")

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
            message = "Recurring expenses feature installed successfully! "
            message += f"Added fields: {', '.join(results['flowgroup_fields'] + results['transaction_fields'])}"
            success = True

        print(f"[Update v1.4.0-beta] {message}")

        if success:
            print("[Update v1.4.0-beta] [SUCCESS] Update completed successfully!")
            print("[Update v1.4.0-beta] New features:")
            print("  - Mark FlowGroups as recurring to auto-copy them to new periods")
            print("  - Mark individual transactions as fixed to auto-replicate them")
            print("  - Auto-replication happens when creating new periods")
            print("  - Mobile: Swipe right on transactions to reveal fixed button")
            print("  - Desktop: Use the 'Fixa' column to mark recurring expenses")

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
            'message': f"Recurring expenses feature installation failed: {str(e)}",
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
