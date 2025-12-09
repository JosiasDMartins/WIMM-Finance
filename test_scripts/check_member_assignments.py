#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wimm_project.settings')
django.setup()

from finances.models import Transaction, FamilyMember, FLOW_TYPE_INCOME
from django.db.models import Sum, Count

# Get first family
family = FamilyMember.objects.first().family

print(f"\nFamily: {family.name}\n")
print("=" * 80)

# Check all family members
print("\nFamily Members:")
for member in FamilyMember.objects.filter(family=family):
    print(f"  {member.user.username} (Role: {member.role})")

print("\n" + "=" * 80)

# Check income transactions grouped by member for recent periods
income_trans = Transaction.objects.filter(
    flow_group__family=family,
    flow_group__group_type=FLOW_TYPE_INCOME,
    realized=True
).order_by('-flow_group__period_start_date', 'member__user__username')

print(f"\nRecent Income Transactions (total: {income_trans.count()}):")
print("=" * 80)

current_period = None
for trans in income_trans[:20]:  # Show last 20 transactions
    period = trans.flow_group.period_start_date
    if period != current_period:
        current_period = period
        print(f"\n--- Period: {period} ---")

    member_name = trans.member.user.username if trans.member else "Family (null)"
    print(f"  ID {trans.id}: {trans.description:30} | {str(trans.amount):15} | Member: {member_name}")

# Check for admin user transactions
print("\n" + "=" * 80)
admin_member = FamilyMember.objects.filter(family=family, role='ADMIN').first()
if admin_member:
    admin_income = Transaction.objects.filter(
        flow_group__family=family,
        flow_group__group_type=FLOW_TYPE_INCOME,
        realized=True,
        member=admin_member
    )
    print(f"\nTransactions assigned to ADMIN user '{admin_member.user.username}': {admin_income.count()}")
    for trans in admin_income:
        print(f"  ID {trans.id}: {trans.description} | {trans.amount} | Period: {trans.flow_group.period_start_date}")
