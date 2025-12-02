# finances/recurring_utils.py
"""
Utilities for handling recurring FlowGroups and fixed transactions.
When a new period is created, this module replicates recurring data.
"""

from datetime import date
from dateutil.relativedelta import relativedelta
from django.db.models import Q
from .models import FlowGroup, Transaction


def ensure_recurring_data_for_period(family, period_start_date):
    """
    Ensures that recurring FlowGroups and fixed transactions exist for the given period.
    If they don't exist, creates them from the most recent previous period.

    This is called when accessing a period to make sure recurring data is up to date.
    Only creates data if it doesn't already exist (idempotent).

    Args:
        family: Family instance
        period_start_date: date object for the period to check

    Returns:
        dict with counts: {
            'groups_created': int,
            'transactions_created': int,
            'already_existed': bool
        }
    """

    # Check if there are any recurring groups from previous periods
    previous_recurring_groups = FlowGroup.objects.filter(
        family=family,
        period_start_date__lt=period_start_date,
        is_recurring=True
    ).order_by('-period_start_date')

    if not previous_recurring_groups.exists():
        return {
            'groups_created': 0,
            'transactions_created': 0,
            'already_existed': True
        }

    # Check which recurring groups already exist in this period
    existing_group_names = set(
        FlowGroup.objects.filter(
            family=family,
            period_start_date=period_start_date
        ).values_list('name', flat=True)
    )

    # Find the most recent version of each recurring group
    seen_groups = set()
    groups_to_check = []

    for group in previous_recurring_groups:
        group_key = (group.name, group.group_type)
        if group_key not in seen_groups:
            seen_groups.add(group_key)
            # Only add if doesn't exist in current period
            if group.name not in existing_group_names:
                groups_to_check.append(group)

    if not groups_to_check:
        return {
            'groups_created': 0,
            'transactions_created': 0,
            'already_existed': True
        }

    # Create missing groups and their fixed transactions
    created_groups = 0
    total_transactions = 0

    for source_group in groups_to_check:
        # Create new FlowGroup
        new_group = FlowGroup.objects.create(
            family=family,
            name=source_group.name,
            group_type=source_group.group_type,
            budgeted_amount=source_group.budgeted_amount,
            period_start_date=period_start_date,
            is_shared=source_group.is_shared,
            is_kids_group=source_group.is_kids_group,
            is_investment=source_group.is_investment,
            is_recurring=True,
            owner=source_group.owner,
            order=source_group.order
        )

        # Copy assigned members for kids groups
        if source_group.is_kids_group:
            new_group.assigned_kids.set(source_group.assigned_kids.all())

        # Copy assigned_members for shared groups (ManyToMany field)
        if source_group.is_shared:
            new_group.assigned_members.set(source_group.assigned_members.all())

            # Also copy shared_with members (FlowGroupAccess relationships)
            # Import FlowGroupAccess model
            from .models import FlowGroupAccess
            # Get all members this group is shared with
            shared_members = source_group.shared_with.all()
            for flow_access in shared_members:
                FlowGroupAccess.objects.create(
                    member=flow_access.member,
                    flow_group=new_group
                )

        created_groups += 1

        # Replicate fixed transactions
        fixed_transactions = Transaction.objects.filter(
            flow_group=source_group,
            is_fixed=True
        )

        for source_transaction in fixed_transactions:
            new_date = _adjust_transaction_date(
                source_transaction.date,
                source_group.period_start_date,
                period_start_date,
                family
            )

            Transaction.objects.create(
                flow_group=new_group,
                description=source_transaction.description,
                amount=source_transaction.amount,
                date=new_date,
                realized=False,
                is_fixed=True,
                member=source_transaction.member,
                order=source_transaction.order
            )

            total_transactions += 1

    return {
        'groups_created': created_groups,
        'transactions_created': total_transactions,
        'already_existed': False
    }


def replicate_recurring_flowgroups(family, new_period_start_date):
    """
    Replicates recurring FlowGroups from the most recent period to the new period.

    Args:
        family: Family instance
        new_period_start_date: date object for the new period's start date

    Returns:
        dict with counts: {
            'groups_created': int,
            'transactions_created': int,
            'groups': list of created FlowGroup instances
        }
    """

    # Find the most recent period before this one
    previous_groups = FlowGroup.objects.filter(
        family=family,
        period_start_date__lt=new_period_start_date,
        is_recurring=True
    ).order_by('-period_start_date')

    if not previous_groups.exists():
        return {
            'groups_created': 0,
            'transactions_created': 0,
            'groups': []
        }

    # Group by most recent version of each recurring group
    # We only want the most recent version of each group name
    seen_groups = set()
    groups_to_copy = []

    for group in previous_groups:
        # Use a tuple of identifying characteristics to avoid duplicates
        group_key = (group.name, group.group_type)
        if group_key not in seen_groups:
            seen_groups.add(group_key)
            groups_to_copy.append(group)

    created_groups = []
    total_transactions = 0

    # Calculate month difference for date adjustments
    for source_group in groups_to_copy:
        # Create new FlowGroup with copied properties
        new_group = FlowGroup.objects.create(
            family=family,
            name=source_group.name,
            group_type=source_group.group_type,
            budgeted_amount=source_group.budgeted_amount,
            period_start_date=new_period_start_date,
            is_shared=source_group.is_shared,
            is_kids_group=source_group.is_kids_group,
            is_investment=source_group.is_investment,
            is_recurring=True,  # Maintain recurring status
            owner=source_group.owner,
            order=source_group.order
        )

        # Copy assigned members for kids groups
        if source_group.is_kids_group:
            new_group.assigned_kids.set(source_group.assigned_kids.all())

        # Copy assigned_members for shared groups (ManyToMany field)
        if source_group.is_shared:
            new_group.assigned_members.set(source_group.assigned_members.all())

            # Also copy shared_with members (FlowGroupAccess relationships)
            # Import FlowGroupAccess model
            from .models import FlowGroupAccess
            # Get all members this group is shared with
            shared_members = source_group.shared_with.all()
            for flow_access in shared_members:
                FlowGroupAccess.objects.create(
                    member=flow_access.member,
                    flow_group=new_group
                )

        created_groups.append(new_group)

        # Now replicate fixed transactions from this group
        fixed_transactions = Transaction.objects.filter(
            flow_group=source_group,
            is_fixed=True
        )

        for source_transaction in fixed_transactions:
            # Calculate new date: preserve day, update month/year
            new_date = _adjust_transaction_date(
                source_transaction.date,
                source_group.period_start_date,
                new_period_start_date,
                family
            )

            # Create new transaction with copied properties
            Transaction.objects.create(
                flow_group=new_group,
                description=source_transaction.description,
                amount=source_transaction.amount,
                date=new_date,
                realized=False,  # Reset realized status for new period
                is_fixed=True,  # Maintain fixed status
                member=source_transaction.member,
                order=source_transaction.order
            )

            total_transactions += 1

    return {
        'groups_created': len(created_groups),
        'transactions_created': total_transactions,
        'groups': created_groups
    }


def _adjust_transaction_date(original_date, old_period_start, new_period_start, family):
    """
    Adjusts a transaction date from old period to new period based on period type.

    For Monthly periods:
        - Preserves the day of month, adds months
        - Example: Nov 20 -> Dec 20 (next period)
        - Handles month-end edge cases (Jan 31 -> Feb 28/29)

    For Bi-weekly/Weekly periods:
        - Preserves relative position within period (days offset from period start)
        - Example: If expense was 2 days after period start, new date is 2 days after new period start

    Args:
        original_date: date from the old period
        old_period_start: start date of the old period
        new_period_start: start date of the new period
        family: Family instance to determine period type

    Returns:
        date object for the new period
    """

    # Get period type from family configuration
    try:
        period_type = family.configuration.period_type
    except:
        # Default to Monthly if configuration doesn't exist
        period_type = 'M'

    if period_type == 'M':  # Monthly
        # Calculate how many months to add
        months_diff = (new_period_start.year - old_period_start.year) * 12 + \
                      (new_period_start.month - old_period_start.month)

        # Add months to the original date
        try:
            new_date = original_date + relativedelta(months=months_diff)
        except ValueError:
            # Handle edge case: e.g., Jan 31 -> Feb (no 31st day)
            # Fall back to last day of target month
            temp_date = date(
                year=original_date.year,
                month=original_date.month,
                day=1
            ) + relativedelta(months=months_diff)

            # Get last day of that month
            next_month = temp_date + relativedelta(months=1)
            last_day_of_month = (next_month - relativedelta(days=1)).day

            new_date = date(
                year=temp_date.year,
                month=temp_date.month,
                day=min(original_date.day, last_day_of_month)
            )

    else:  # Bi-weekly ('B') or Weekly ('W')
        # Calculate offset (days from period start)
        days_offset = (original_date - old_period_start).days

        # Add same offset to new period start
        new_date = new_period_start + relativedelta(days=days_offset)

    return new_date
