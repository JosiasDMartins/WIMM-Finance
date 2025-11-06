# finances/utils.py

import datetime
from django.utils import timezone
from django.db import models
from dateutil.relativedelta import relativedelta
from calendar import monthrange
from .models import Transaction, FlowGroup, FamilyMemberRoleHistory, ClosedPeriod

def get_current_period_dates(family, query_period=None):
    """
    Determines the start and end dates of the financial period.
    If query_period is provided (format: YYYY-MM-DD), uses that date to calculate the period.
    Otherwise uses today's date.
    
    Now supports Monthly (M), Bi-weekly (B), and Weekly (W) periods.
    """
    config = getattr(family, 'configuration', None)
    
    # Determine reference date
    if query_period:
        try:
            # Parse query_period as date string (YYYY-MM-DD format)
            reference_date = datetime.datetime.strptime(query_period, '%Y-%m-%d').date()
        except ValueError:
            reference_date = timezone.localdate()
    else:
        reference_date = timezone.localdate()

    # Check if this date falls within a closed period
    closed_period = ClosedPeriod.objects.filter(
        family=family,
        start_date__lte=reference_date,
        end_date__gte=reference_date
    ).first()
    
    if closed_period:
        # Return the closed period boundaries
        period_label = f"{closed_period.start_date.strftime('%b %d')} - {closed_period.end_date.strftime('%b %d, %Y')}"
        return closed_period.start_date, closed_period.end_date, period_label
    
    if not config:
        # Default to standard calendar month if no config
        start_date = reference_date.replace(day=1)
        try:
            end_date = reference_date.replace(month=reference_date.month + 1, day=1) - datetime.timedelta(days=1)
        except ValueError:
            end_date = reference_date.replace(year=reference_date.year + 1, month=1, day=1) - datetime.timedelta(days=1)
        period_label = start_date.strftime("%B %Y")
        return start_date, end_date, period_label
    
    period_type = config.period_type
    
    if period_type == 'M':
        # Monthly period logic
        starting_day = config.starting_day
        
        if reference_date.day >= starting_day:
            # Period starts this month
            start_date = reference_date.replace(day=starting_day)
            next_month = start_date + relativedelta(months=1)
            last_day_next_month = monthrange(next_month.year, next_month.month)[1]
            day_to_use = min(starting_day, last_day_next_month)
            end_date = next_month.replace(day=day_to_use) - relativedelta(days=1)
        else:
            # Period started last month
            prev_month = reference_date.replace(day=1) - relativedelta(days=1)
            start_date = prev_month.replace(day=starting_day)
            end_date = reference_date.replace(day=starting_day) - relativedelta(days=1)
    
    elif period_type == 'B':
        # Bi-weekly period logic (14 days)
        base_date = config.base_date
        days_diff = (reference_date - base_date).days
        
        # Calculate which bi-weekly period we're in
        period_number = days_diff // 14
        
        start_date = base_date + datetime.timedelta(days=period_number * 14)
        end_date = start_date + datetime.timedelta(days=13)  # 14 days total (0-13)
    
    elif period_type == 'W':
        # Weekly period logic (7 days)
        base_date = config.base_date
        days_diff = (reference_date - base_date).days
        
        # Calculate which weekly period we're in
        period_number = days_diff // 7
        
        start_date = base_date + datetime.timedelta(days=period_number * 7)
        end_date = start_date + datetime.timedelta(days=6)  # 7 days total (0-6)
    
    else:
        # Fallback to calendar month
        start_date = reference_date.replace(day=1)
        try:
            end_date = reference_date.replace(month=reference_date.month + 1, day=1) - datetime.timedelta(days=1)
        except ValueError:
            end_date = reference_date.replace(year=reference_date.year + 1, month=1, day=1) - datetime.timedelta(days=1)

    # Generate label
    if start_date.year == end_date.year and start_date.month == end_date.month:
        period_label = start_date.strftime("%B %Y")
    else:
        period_label = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"

    return start_date, end_date, period_label


def get_available_periods(family):
    """
    Returns list of available periods for selection based on actual data.
    Shows periods where transactions exist + one empty period before the earliest data.
    Also includes all closed periods.
    """
    config = getattr(family, 'configuration', None)
    if not config:
        return []
    
    today = timezone.localdate()
    periods = []
    
    # Get all closed periods first
    closed_periods = ClosedPeriod.objects.filter(family=family).order_by('-start_date')
    for closed in closed_periods:
        period_label = f"{closed.start_date.strftime('%b %d')} - {closed.end_date.strftime('%b %d, %Y')}"
        has_data = Transaction.objects.filter(
            flow_group__family=family,
            date__range=(closed.start_date, closed.end_date)
        ).exists()
        
        periods.append({
            'label': period_label,
            'value': closed.start_date.strftime('%Y-%m-%d'),
            'start_date': closed.start_date,
            'end_date': closed.end_date,
            'is_current': False,  # Closed periods are never current
            'has_data': has_data,
            'is_closed': True
        })
    
    # Get all unique transaction dates (not FlowGroup period_start_dates)
    transaction_dates = Transaction.objects.filter(
        flow_group__family=family
    ).values_list('date', flat=True).distinct().order_by('-date')
    
    # Get current period
    current_start, current_end, current_label = get_current_period_dates(family, None)
    
    if not transaction_dates:
        # No data exists - show current period and one previous period
        periods.append({
            'label': current_label,
            'value': current_start.strftime('%Y-%m-%d'),
            'start_date': current_start,
            'end_date': current_end,
            'is_current': True,
            'has_data': False,
            'is_closed': False
        })
        
        # Add one previous empty period
        if config.period_type == 'M':
            prev_ref = today - relativedelta(months=1)
        elif config.period_type == 'B':
            prev_ref = today - datetime.timedelta(days=14)
        else:  # Weekly
            prev_ref = today - datetime.timedelta(days=7)
        
        prev_start, prev_end, prev_label = get_current_period_dates(family, prev_ref.strftime('%Y-%m-%d'))
        
        # Check if not already in closed periods
        if not any(p['value'] == prev_start.strftime('%Y-%m-%d') for p in periods):
            periods.append({
                'label': prev_label,
                'value': prev_start.strftime('%Y-%m-%d'),
                'start_date': prev_start,
                'end_date': prev_end,
                'is_current': False,
                'has_data': False,
                'is_closed': False
            })
        
        return periods
    
    # Find all periods that contain transaction dates (excluding closed periods)
    periods_with_data = set()
    for trans_date in transaction_dates:
        # Skip if date is in a closed period
        if any(p['start_date'] <= trans_date <= p['end_date'] for p in periods if p.get('is_closed')):
            continue
            
        period_start, period_end, _ = get_current_period_dates(family, trans_date.strftime('%Y-%m-%d'))
        periods_with_data.add(period_start)
    
    # Convert to sorted list (most recent first)
    periods_with_data = sorted(periods_with_data, reverse=True)
    
    # Build periods list for non-closed periods
    for period_start in periods_with_data:
        # Skip if already in closed periods
        if any(p['value'] == period_start.strftime('%Y-%m-%d') for p in periods if p.get('is_closed')):
            continue
            
        _, period_end, period_label = get_current_period_dates(family, period_start.strftime('%Y-%m-%d'))
        
        # Check if this period has actual data
        has_data = Transaction.objects.filter(
            flow_group__family=family,
            date__range=(period_start, period_end)
        ).exists()
        
        periods.append({
            'label': period_label,
            'value': period_start.strftime('%Y-%m-%d'),
            'start_date': period_start,
            'end_date': period_end,
            'is_current': (period_start == current_start),
            'has_data': has_data,
            'is_closed': False
        })
    
    # Ensure current period is always included (even if no data)
    if not any(p['value'] == current_start.strftime('%Y-%m-%d') for p in periods):
        periods.insert(0, {
            'label': current_label,
            'value': current_start.strftime('%Y-%m-%d'),
            'start_date': current_start,
            'end_date': current_end,
            'is_current': True,
            'has_data': False,
            'is_closed': False
        })
    
    # Add one empty period before the earliest data
    if periods_with_data:
        earliest_period = min(periods_with_data)
        
        if config.period_type == 'M':
            prev_ref = earliest_period - relativedelta(months=1)
        elif config.period_type == 'B':
            prev_ref = earliest_period - datetime.timedelta(days=14)
        else:  # Weekly
            prev_ref = earliest_period - datetime.timedelta(days=7)
        
        prev_start, prev_end, prev_label = get_current_period_dates(family, prev_ref.strftime('%Y-%m-%d'))
        
        # Check if this period already exists
        if not any(p['value'] == prev_start.strftime('%Y-%m-%d') for p in periods):
            periods.append({
                'label': prev_label,
                'value': prev_start.strftime('%Y-%m-%d'),
                'start_date': prev_start,
                'end_date': prev_end,
                'is_current': False,
                'has_data': False,
                'is_closed': False
            })
    
    # Sort by start_date descending (most recent first)
    periods.sort(key=lambda x: x['start_date'], reverse=True)
    
    return periods


def user_can_access_flow_group(user, flow_group):
    """
    Checks if the user has access to the FlowGroup (owner or Family Admin).
    """
    if flow_group.owner == user:
        return True
    
    try:
        member = user.memberships.get(family=flow_group.family)
        if member.role == 'ADMIN':
            return True
    except:
        pass
    
    return False


def get_member_role_for_period(member, period_start_date):
    """
    Gets the role a member had during a specific period.
    Uses FamilyMemberRoleHistory to track historical roles.
    Falls back to current role if no history exists.
    """
    try:
        # Try to get historical role for this period
        role_history = FamilyMemberRoleHistory.objects.filter(
            member=member,
            period_start_date__lte=period_start_date
        ).order_by('-period_start_date').first()
        
        if role_history:
            return role_history.role
    except:
        pass
    
    # Fallback to current role
    return member.role


def save_role_history_if_changed(member, new_role, period_start_date):
    """
    Saves role history if the role changed.
    Should be called when updating a member's role.
    """
    # Get current role for this period
    current_role = get_member_role_for_period(member, period_start_date)
    
    # If role changed, save history
    if current_role != new_role:
        FamilyMemberRoleHistory.objects.update_or_create(
            member=member,
            period_start_date=period_start_date,
            defaults={'role': new_role}
        )
        
        # Update member's current role
        member.role = new_role
        member.save()


def close_current_period(family):
    """
    Closes the current period by creating a ClosedPeriod record.
    Should be called when period settings are about to change.
    Returns the closed period object.
    """
    config = family.configuration
    current_start, current_end, _ = get_current_period_dates(family, None)
    
    # Check if already closed
    existing = ClosedPeriod.objects.filter(
        family=family,
        start_date=current_start
    ).first()
    
    if existing:
        return existing
    
    # Create closed period
    closed = ClosedPeriod.objects.create(
        family=family,
        start_date=current_start,
        end_date=current_end,
        period_type=config.period_type
    )
    
    return closed


def check_period_change_impact(family, new_period_type, new_starting_day=None, new_base_date=None):
    """
    Analyzes the impact of changing period settings.
    Returns a dict with:
    - 'requires_close': bool - if current period needs to be closed
    - 'current_period': tuple - (start_date, end_date, label)
    - 'new_current_period': tuple - (start_date, end_date, label) after change
    - 'message': str - warning message for user
    """
    config = family.configuration
    old_type = config.period_type
    old_starting_day = config.starting_day
    old_base_date = config.base_date
    
    # Get current period with old settings
    current_start, current_end, current_label = get_current_period_dates(family, None)
    
    # Temporarily apply new settings to calculate new period
    config.period_type = new_period_type
    if new_starting_day:
        config.starting_day = new_starting_day
    if new_base_date:
        config.base_date = new_base_date
    
    # Calculate new current period
    new_start, new_end, new_label = get_current_period_dates(family, None)
    
    # Restore old settings (don't save)
    config.period_type = old_type
    config.starting_day = old_starting_day
    config.base_date = old_base_date
    
    # Determine if we need to close the current period
    requires_close = False
    message = ""
    
    # Check if dates changed
    if old_type == new_period_type and old_type == 'M':
        # Monthly to Monthly with different starting day
        if new_starting_day and new_starting_day != old_starting_day:
            requires_close = True
            message = f"Changing starting day will adjust the current period. Previous period may have more or fewer days. Current period: {current_label}. Review your entries after this change."
    
    elif old_type != new_period_type:
        # Period type is changing
        today = timezone.localdate()
        
        # Check if new period boundaries would split current period
        if new_start > current_start or new_end < current_end:
            requires_close = True
            message = f"Changing from {config.get_period_type_display()} to {dict(config.PERIOD_TYPES)[new_period_type]} will close the current period on {current_end.strftime('%b %d, %Y')}. A new period will start on {new_start.strftime('%b %d, %Y')}. Please review your entries to ensure they're in the correct period."
        else:
            requires_close = True
            message = f"Changing period type from {config.get_period_type_display()} to {dict(config.PERIOD_TYPES)[new_period_type]}. The current period will be adjusted. Please review your entries."
    
    return {
        'requires_close': requires_close,
        'current_period': (current_start, current_end, current_label),
        'new_current_period': (new_start, new_end, new_label),
        'message': message
    }


def copy_flow_groups_to_new_period(family, old_period_start, new_period_start, new_period_end):
    """
    Copies FlowGroups from old period to new period.
    Distributes transactions based on their dates:
    - Transactions before new period start stay in old period
    - Transactions within new period move to new period's FlowGroup copy
    
    Returns count of groups copied.
    """
    from django.db import transaction as db_transaction
    
    with db_transaction.atomic():
        # Get all FlowGroups from old period
        old_flow_groups = FlowGroup.objects.filter(
            family=family,
            period_start_date=old_period_start
        )
        
        groups_copied = 0
        
        for old_group in old_flow_groups:
            # Create copy for new period with new period_start_date
            new_group = FlowGroup.objects.create(
                name=old_group.name,
                family=old_group.family,
                owner=old_group.owner,
                group_type=old_group.group_type,
                budgeted_amount=old_group.budgeted_amount,
                period_start_date=new_period_start,
                is_shared=old_group.is_shared,
                is_kids_group=old_group.is_kids_group,
                realized=False,  # Reset realized for new period
                is_investment=old_group.is_investment,
                order=old_group.order
            )
            
            # Copy assigned members and children
            new_group.assigned_members.set(old_group.assigned_members.all())
            new_group.assigned_children.set(old_group.assigned_children.all())
            
            # Get transactions from old group
            old_transactions = Transaction.objects.filter(flow_group=old_group)
            
            # Move transactions that fall within new period to new group
            for transaction in old_transactions:
                if new_period_start <= transaction.date <= new_period_end:
                    # Move to new group
                    transaction.flow_group = new_group
                    transaction.save()
            
            groups_copied += 1
        
        return groups_copied


def copy_previous_period_data(family, exclude_child_data=True):
    """
    Copies all FlowGroups and Transactions from previous period to current period.
    Updates dates to current date.
    Excludes data created by CHILD users if exclude_child_data=True.
    
    Returns dict with counts of items copied.
    """
    from django.db import transaction as db_transaction
    from .models import FamilyMember
    
    with db_transaction.atomic():
        # Get current period
        current_start, current_end, _ = get_current_period_dates(family, None)
        
        # Get previous period
        config = family.configuration
        if config.period_type == 'M':
            prev_ref = current_start - relativedelta(months=1)
        elif config.period_type == 'B':
            prev_ref = current_start - datetime.timedelta(days=14)
        else:  # Weekly
            prev_ref = current_start - datetime.timedelta(days=7)
        
        prev_start, prev_end, _ = get_current_period_dates(family, prev_ref.strftime('%Y-%m-%d'))
        
        # Get FlowGroups from previous period
        prev_groups = FlowGroup.objects.filter(
            family=family,
            period_start_date=prev_start
        )
        
        groups_copied = 0
        transactions_copied = 0
        today = timezone.localdate()
        
        for old_group in prev_groups:
            # Check if group already exists in current period
            existing = FlowGroup.objects.filter(
                family=family,
                name=old_group.name,
                period_start_date=current_start
            ).first()
            
            if existing:
                # Use existing group
                new_group = existing
            else:
                # Create new group
                new_group = FlowGroup.objects.create(
                    name=old_group.name,
                    family=old_group.family,
                    owner=old_group.owner,
                    group_type=old_group.group_type,
                    budgeted_amount=old_group.budgeted_amount,
                    period_start_date=current_start,
                    is_shared=old_group.is_shared,
                    is_kids_group=old_group.is_kids_group,
                    realized=False,
                    is_investment=old_group.is_investment,
                    order=old_group.order
                )
                
                # Copy assigned members and children
                new_group.assigned_members.set(old_group.assigned_members.all())
                new_group.assigned_children.set(old_group.assigned_children.all())
                groups_copied += 1
            
            # Copy transactions
            old_transactions = Transaction.objects.filter(flow_group=old_group)
            
            for old_trans in old_transactions:
                # Skip child manual income and child expenses if requested
                if exclude_child_data:
                    if old_trans.is_child_manual_income or old_trans.is_child_expense:
                        continue
                
                # Get max order for new group
                max_order = Transaction.objects.filter(flow_group=new_group).aggregate(
                    max_order=models.Max('order')
                )['max_order'] or 0
                
                # Create copy with today's date
                Transaction.objects.create(
                    description=old_trans.description,
                    amount=old_trans.amount,
                    date=today,
                    realized=False,  # Reset realized
                    is_child_manual_income=False,
                    is_child_expense=False,
                    member=old_trans.member,
                    flow_group=new_group,
                    order=max_order + 1
                )
                transactions_copied += 1
        
        return {
            'groups_copied': groups_copied,
            'transactions_copied': transactions_copied
        }


def current_period_has_data(family):
    """
    Checks if current period has any transactions.
    Returns True if there's data, False if empty.
    """
    current_start, current_end, _ = get_current_period_dates(family, None)
    
    # Check for any transactions in current period
    has_transactions = Transaction.objects.filter(
        flow_group__family=family,
        date__range=(current_start, current_end)
    ).exists()
    
    return has_transactions
