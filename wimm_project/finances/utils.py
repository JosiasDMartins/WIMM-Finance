# finances/utils.py

import datetime
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from calendar import monthrange
from .models import Transaction

def get_current_period_dates(family, query_period=None):
    """
    Determines the start and end dates of the current financial period 
    based on the FamilyConfiguration and an optional period query.

    NOTE: Currently only implements 'Monthly' cycle based on starting_day.
    """
    today = timezone.localdate()
    
    # Check for configuration existence 
    config = getattr(family, 'configuration', None)

    # Determine start and end date for the current period

    if config and config.period_type == 'M':
        # Monthly cycle based on starting_day
        starting_day = config.starting_day
        
        # Determine if we're in the current period or a previous one
        if today.day >= starting_day:
            # We're in a period that started this month
            start_date = today.replace(day=starting_day)
            # Period ends on the day before starting_day of next month
            next_month = start_date + relativedelta(months=1)
            last_day_next_month = monthrange(next_month.year, next_month.month)[1]
            day_to_use = min(starting_day, last_day_next_month)
            end_date = next_month.replace(day=day_to_use) - relativedelta(days=1)
        else:
            # We're in a period that started last month
            start_date = (today.replace(day=1) - relativedelta(days=1)).replace(day=starting_day)
            # Period ends on the day before starting_day of this month
            end_date = today.replace(day=starting_day) - relativedelta(days=1)
            
    else:
        # Default to standard calendar month (day 1 to last day of month)
        start_date = today.replace(day=1)
        
        # Calculate last day of the month
        try:
            # Safer way to get the last day of the month
            end_date = today.replace(month=today.month + 1, day=1) - datetime.timedelta(days=1)
        except ValueError: # If month is 12, need to handle year rollover
            end_date = today.replace(year=today.year + 1, month=1, day=1) - datetime.timedelta(days=1)

    # --- Period Label ---
    # Used in dashboard.html to display the period
    if start_date.year == end_date.year and start_date.month == end_date.month:
        # Standard calendar month label (e.g., October 2025)
        current_period_label = start_date.strftime("%B %Y")
    else:
        # Cross-month label (e.g., Sep 6 - Oct 5, 2025)
        current_period_label = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"

    return start_date, end_date, current_period_label


def get_available_periods(family):
    """
    Returns list of available periods for selection.
    Shows current period + previous periods with data + one empty period before the first data.
    
    Logic:
    - Always show current period
    - Show all previous periods that have transactions
    - Show one additional empty period before the oldest period with data
    """
    config = getattr(family, 'configuration', None)
    if not config:
        return []
    
    today = timezone.localdate()
    periods = []
    
    # Get the oldest transaction date for this family
    oldest_transaction = Transaction.objects.filter(
        flow_group__family=family
    ).order_by('date').first()
    
    if not oldest_transaction:
        # No transactions yet - show only current period and one previous
        current_start, current_end, current_label = get_period_dates_for_month(today, config)
        periods.append({
            'label': current_label,
            'value': current_start.strftime('%Y-%m'),
            'start_date': current_start,
            'end_date': current_end,
            'is_current': True,
            'has_data': False
        })
        
        # Add one empty previous period
        prev_date = current_start - relativedelta(months=1)
        prev_start, prev_end, prev_label = get_period_dates_for_month(prev_date, config)
        periods.append({
            'label': prev_label,
            'value': prev_start.strftime('%Y-%m'),
            'start_date': prev_start,
            'end_date': prev_end,
            'is_current': False,
            'has_data': False
        })
        
        return periods
    
    # Start from current period and work backwards
    current_start, current_end, current_label = get_period_dates_for_month(today, config)
    cursor_date = today
    
    # Track if we've found the last period with data
    found_last_data_period = False
    periods_after_last_data = 0
    
    # Go back up to 24 months or until we've added one empty period after last data
    for i in range(24):
        period_start, period_end, period_label = get_period_dates_for_month(cursor_date, config)
        
        # Check if this period has transactions
        has_transactions = Transaction.objects.filter(
            flow_group__family=family,
            date__range=(period_start, period_end)
        ).exists()
        
        is_current = (period_start == current_start)
        
        periods.append({
            'label': period_label,
            'value': period_start.strftime('%Y-%m'),
            'start_date': period_start,
            'end_date': period_end,
            'is_current': is_current,
            'has_data': has_transactions
        })
        
        # Track empty periods after last data
        if not has_transactions and not is_current:
            if found_last_data_period:
                periods_after_last_data += 1
                # Stop after adding one empty period after last data
                if periods_after_last_data >= 1:
                    break
        else:
            if has_transactions:
                found_last_data_period = True
                periods_after_last_data = 0
        
        # Move to previous month
        cursor_date = cursor_date - relativedelta(months=1)
    
    return periods


def get_period_dates_for_month(reference_date, config):
    """
    Calculate period start and end dates for a given reference date.
    """
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
    
    # Generate label
    if start_date.year == end_date.year and start_date.month == end_date.month:
        period_label = start_date.strftime("%B %Y")
    else:
        period_label = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
    
    return start_date, end_date, period_label


def get_period_options_context(family, current_start_date):
    """
    DEPRECATED: Use get_available_periods instead.
    Kept for backward compatibility.
    """
    return get_available_periods(family)


def user_can_access_flow_group(user, flow_group):
    """
    Checks if the user has access to the FlowGroup (owner or Family Admin).
    
    NOTE: Does not check FlowGroupAccess model yet, as per original file structure.
    """
    # 1. Check if the user is the owner of the FlowGroup
    if flow_group.owner == user:
        return True
    
    # 2. Check if the user is an Admin of the Family
    try:
        member = user.memberships.get(family=flow_group.family)
        if member.role == 'ADMIN':
            return True
    except:
        pass # User is not a member of the family
    
    return False