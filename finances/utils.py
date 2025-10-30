# finances/utils.py

import datetime
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from calendar import monthrange

def get_current_period_dates(family, query_period=None):
    """
    Determines the start and end dates of the current financial period 
    based on the FamilyConfiguration and an optional period query.

    NOTE: Currently only implements 'Monthly' cycle based on closing_day.
    """
    today = timezone.localdate()
    
    # Check for configuration existence 
    config = getattr(family, 'configuration', None)

    # Determine start and end date for the current period

    if config and config.period_type == 'M':
        # Monthly cycle based on closing_day
        closing_day = config.closing_day
        
        # Determine the target month for the end date.
        # If today's day is before or equal to the closing day, the cycle ends this month.
        if today.day <= closing_day:
            # Cycle ends this month (on closing_day)
            end_date = today.replace(day=closing_day)
            # Cycle starts on the day after the closing day of the previous month.
            start_date = end_date - relativedelta(months=1) + relativedelta(days=1)
        else:
            # Cycle starts this month (on day after closing_day)
            start_date = today.replace(day=closing_day) + relativedelta(days=1)
            # Cycle ends on the closing day of the next month.
            
            # Find the date one month from the start_date
            next_month_ref = start_date + relativedelta(months=1)
            
            # Ensure the closing day is valid for the target month
            last_day_next_month = monthrange(next_month_ref.year, next_month_ref.month)[1]
            day_to_use = min(closing_day, last_day_next_month)
            end_date = next_month_ref.replace(day=day_to_use)
            
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

def get_period_options_context(family, current_start_date):
    """
    Generates a list of periods for the dashboard dropdown.
    Currently generates the last 7 periods (current + 6 previous).
    """
    periods = []
    date_cursor = current_start_date
    
    # Simplification: generate options based on calendar months for now
    for i in range(7):
        # Value for query can be Year-Month (used by dashboard view to fetch the period)
        label = date_cursor.strftime("%B %Y")
        value = date_cursor.strftime("%Y-%m")
        
        periods.append({
            'label': label,
            'value': value,
        })
        
        # Move back one calendar month
        date_cursor = date_cursor - relativedelta(months=1)

    # Reverse to show most recent first (current period is the latest)
    return periods[::-1]


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