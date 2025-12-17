"""
FlowGroup utility functions for copying and managing flow groups.

This module handles FlowGroup-related operations including:
- Copying FlowGroups between periods
- Applying period configuration changes
"""

import logging
from django.utils import timezone

from ..models import FlowGroup, Transaction
from .currency_utils import ensure_period_exists

logger = logging.getLogger(__name__)


def copy_previous_period_data(family, old_period_start, new_period_start, new_period_end):
    """
    Copies FlowGroups and their structure from one period to another.
    Also moves transactions that belong to the new period.

    Returns the number of FlowGroups copied.
    """
    # Get all FlowGroups from the old period
    old_flow_groups = FlowGroup.objects.filter(
        family=family,
        period_start_date=old_period_start
    )

    copied_count = 0

    for old_group in old_flow_groups:
        # Check if already exists in new period
        existing = FlowGroup.objects.filter(
            family=family,
            name=old_group.name,
            period_start_date=new_period_start
        ).first()

        if not existing:
            # Create new FlowGroup for new period
            new_group = FlowGroup.objects.create(
                family=family,
                owner=old_group.owner,
                name=old_group.name,
                group_type=old_group.group_type,
                budgeted_amount=old_group.budgeted_amount,
                period_start_date=new_period_start,
                is_shared=old_group.is_shared,
                is_kids_group=old_group.is_kids_group,
                realized=False,  # Reset realized status
                is_investment=old_group.is_investment,
                is_credit_card=old_group.is_credit_card,  # Copy credit card flag
                closed=False,  # Reset closed status for new period
                order=old_group.order
            )

            # Copy assigned members and children
            new_group.assigned_members.set(old_group.assigned_members.all())
            new_group.assigned_children.set(old_group.assigned_children.all())

            copied_count += 1

            # Move transactions that belong to the new period
            transactions_to_move = Transaction.objects.filter(
                flow_group=old_group,
                date__gte=new_period_start,
                date__lte=new_period_end
            )

            transactions_to_move.update(flow_group=new_group)

    return copied_count


def apply_period_configuration_change(family, old_config, new_config, adjustment_period=None):
    """
    Applies period configuration changes by creating Period entries and copying FlowGroups.
    Also adjusts future transactions to the start of the new current period.

    Args:
        family: Family instance
        old_config: dict with old configuration values
        new_config: dict with new configuration values
        adjustment_period: tuple (start_date, end_date) if adjustment period is needed

    Returns:
        dict with operation results
    """
    today = timezone.localdate()

    # Get OLD current period boundaries
    current_start = old_config['current_start']
    current_end = old_config['current_end']

    # Get NEW period boundaries
    new_start = new_config['new_start']
    new_end = new_config['new_end']

    results = {
        'periods_created': [],
        'flow_groups_copied': 0,
        'transactions_moved': 0,
        'future_transactions_adjusted': 0
    }

    # FIRST: Adjust any future transactions (beyond new period end) to new period start
    future_transactions = Transaction.objects.filter(
        flow_group__family=family,
        date__gt=new_end
    )

    if future_transactions.exists():
        future_count = future_transactions.count()
        future_transactions.update(date=new_start)
        results['future_transactions_adjusted'] = future_count

    # Get current currency from family configuration
    current_currency = family.configuration.base_currency if hasattr(family, 'configuration') else 'USD'

    if adjustment_period:
        # Create an adjustment period
        adj_start, adj_end = adjustment_period

        # Ensure Period exists for adjustment period
        period = ensure_period_exists(family, adj_start, adj_end, old_config['period_type'])
        period.currency = current_currency
        period.save()
        results['periods_created'].append(period)

        # Copy FlowGroups from current period to adjustment period
        copied = copy_previous_period_data(
            family,
            current_start,  # Source period
            adj_start,      # Target period start
            adj_end         # Target period end
        )
        results['flow_groups_copied'] += copied

    else:
        # No adjustment period, but current period boundaries changed
        if new_start != current_start:
            # Create Period for the old current period with its original boundaries
            adj_end = new_start - timezone.timedelta(days=1)

            period = ensure_period_exists(family, current_start, adj_end, old_config['period_type'])
            period.currency = current_currency
            period.save()
            results['periods_created'].append(period)

    # Ensure Period exists for the NEW current period
    new_period = ensure_period_exists(family, new_start, new_end, new_config['period_type'])
    new_period.currency = current_currency
    new_period.save()

    # Copy FlowGroups to the NEW current period
    copied = copy_previous_period_data(
        family,
        current_start,  # Source period
        new_start,      # New period start
        new_end         # New period end
    )
    results['flow_groups_copied'] += copied

    return results
