# finances/utils.py

import datetime
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from calendar import monthrange
from .models import Transaction, FlowGroup, FamilyMemberRoleHistory

def get_current_period_dates(family, query_period=None):
    """
    Determines the start and end dates of the financial period.
    If query_period is provided (format: YYYY-MM-DD), uses that date to calculate the period.
    Otherwise uses today's date.
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

    if config and config.period_type == 'M':
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
    else:
        # Default to standard calendar month
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
    """
    config = getattr(family, 'configuration', None)
    if not config:
        return []
    
    today = timezone.localdate()
    periods = []
    
    # Get all unique transaction dates (not FlowGroup period_start_dates)
    transaction_dates = Transaction.objects.filter(
        flow_group__family=family
    ).values_list('date', flat=True).distinct().order_by('-date')
    
    if not transaction_dates:
        # No data exists - show current period and one previous period
        current_start, current_end, current_label = get_current_period_dates(family, None)
        
        periods.append({
            'label': current_label,
            'value': current_start.strftime('%Y-%m-%d'),
            'start_date': current_start,
            'end_date': current_end,
            'is_current': True,
            'has_data': False
        })
        
        # Add one previous empty period
        prev_month_ref = today - relativedelta(months=1)
        prev_start, prev_end, prev_label = get_current_period_dates(family, prev_month_ref.strftime('%Y-%m-%d'))
        periods.append({
            'label': prev_label,
            'value': prev_start.strftime('%Y-%m-%d'),
            'start_date': prev_start,
            'end_date': prev_end,
            'is_current': False,
            'has_data': False
        })
        
        return periods
    
    # Get current period
    current_start, current_end, current_label = get_current_period_dates(family, None)
    
    # Find all periods that contain transaction dates
    periods_with_data = set()
    for trans_date in transaction_dates:
        period_start, period_end, _ = get_current_period_dates(family, trans_date.strftime('%Y-%m-%d'))
        periods_with_data.add(period_start)
    
    # Convert to sorted list (most recent first)
    periods_with_data = sorted(periods_with_data, reverse=True)
    
    # Build periods list
    for period_start in periods_with_data:
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
            'has_data': has_data
        })
    
    # Ensure current period is always included (even if no data)
    if not any(p['value'] == current_start.strftime('%Y-%m-%d') for p in periods):
        periods.insert(0, {
            'label': current_label,
            'value': current_start.strftime('%Y-%m-%d'),
            'start_date': current_start,
            'end_date': current_end,
            'is_current': True,
            'has_data': False
        })
    
    # Add one empty period before the earliest data
    if periods_with_data:
        earliest_period = min(periods_with_data)
        prev_month_ref = earliest_period - relativedelta(months=1)
        prev_start, prev_end, prev_label = get_current_period_dates(family, prev_month_ref.strftime('%Y-%m-%d'))
        
        # Check if this period already exists
        if not any(p['value'] == prev_start.strftime('%Y-%m-%d') for p in periods):
            periods.append({
                'label': prev_label,
                'value': prev_start.strftime('%Y-%m-%d'),
                'start_date': prev_start,
                'end_date': prev_end,
                'is_current': False,
                'has_data': False
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
