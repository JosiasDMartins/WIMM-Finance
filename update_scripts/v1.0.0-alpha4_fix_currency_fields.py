"""
Update Script: Currency Fields Fix
Version: 1.0.0-alpha3
Description: Fixes all currency fields in existing database records

This script sets default currency (BRL) for all records that don't have one.
Prevents "This field is required" errors for MoneyField objects.
"""

from decimal import Decimal
from django.db import transaction


def run():
    """
    Main execution function.
    Must return a dict with:
        - success: bool
        - message: str
        - details: dict (optional)
    """
    try:
        # Import models here to avoid circular imports
        from finances.models import (
            FamilyConfiguration, FlowGroup, Transaction,
            Investment, BankBalance
        )
        
        results = {
            'FamilyConfiguration': 0,
            'FlowGroup': 0,
            'Transaction': 0,
            'Investment': 0,
            'BankBalance': 0
        }
        
        with transaction.atomic():
            # Fix FamilyConfiguration
            for config in FamilyConfiguration.objects.all():
                if not config.base_currency or config.base_currency == '':
                    config.base_currency = 'BRL'
                    config.save(update_fields=['base_currency'])
                    results['FamilyConfiguration'] += 1
            
            # Fix FlowGroup budgeted_amount
            for flow_group in FlowGroup.objects.all():
                updated = False
                if not flow_group.budgeted_amount_currency or flow_group.budgeted_amount_currency == '':
                    flow_group.budgeted_amount_currency = 'BRL'
                    updated = True
                if flow_group.budgeted_amount is None:
                    flow_group.budgeted_amount = Decimal('0.00')
                    updated = True
                if updated:
                    flow_group.save()
                    results['FlowGroup'] += 1
            
            # Fix Transaction amount
            for txn in Transaction.objects.all():
                updated = False
                if not txn.amount_currency or txn.amount_currency == '':
                    txn.amount_currency = 'BRL'
                    updated = True
                if txn.amount is None:
                    txn.amount = Decimal('0.00')
                    updated = True
                if updated:
                    txn.save()
                    results['Transaction'] += 1
            
            # Fix Investment amount
            for investment in Investment.objects.all():
                updated = False
                if not investment.amount_currency or investment.amount_currency == '':
                    investment.amount_currency = 'BRL'
                    updated = True
                if investment.amount is None:
                    investment.amount = Decimal('0.00')
                    updated = True
                if updated:
                    investment.save()
                    results['Investment'] += 1
            
            # Fix BankBalance amount
            for bank_balance in BankBalance.objects.all():
                updated = False
                if not bank_balance.amount_currency or bank_balance.amount_currency == '':
                    bank_balance.amount_currency = 'BRL'
                    updated = True
                if bank_balance.amount is None:
                    bank_balance.amount = Decimal('0.00')
                    updated = True
                if updated:
                    bank_balance.save()
                    results['BankBalance'] += 1
        
        # Build success message
        total_fixed = sum(results.values())
        
        if total_fixed == 0:
            message = "No records needed currency fixes"
        else:
            details = ', '.join([f"{k}: {v}" for k, v in results.items() if v > 0])
            message = f"Fixed {total_fixed} records ({details})"
        
        return {
            'success': True,
            'message': message,
            'details': results
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f"Currency fix failed: {str(e)}",
            'error': str(e)
        }


# For testing purposes
if __name__ == "__main__":
    import os
    import sys
    import django
    
    # Setup Django environment
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')
    django.setup()
    
    # Run the update
    result = run()
    print(f"Success: {result['success']}")
    print(f"Message: {result['message']}")
    if 'details' in result:
        print(f"Details: {result['details']}")
