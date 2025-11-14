# finances/utils.py

import datetime
from django.utils import timezone
from django.db import models
from dateutil.relativedelta import relativedelta
from calendar import monthrange
from .models import Transaction, FlowGroup, FamilyMemberRoleHistory, Period


def get_period_currency(family, period_start_date):
    """
    Retorna a moeda para um período específico.
    Consulta primeiro a tabela Period. Se não existir entrada, usa base_currency da família.
    """
    period = Period.objects.filter(
        family=family,
        start_date=period_start_date
    ).first()
    
    if period:
        return period.currency
    
    # Se não existe período registrado, usa moeda padrão da família
    config = getattr(family, 'configuration', None)
    if config:
        return config.base_currency
    
    return 'USD'  # Fallback padrão


def ensure_period_exists(family, start_date, end_date, period_type):
    """
    Garante que existe uma entrada de Period para o período especificado.
    Se não existir, cria uma nova com a moeda padrão da família.
    
    Returns: Period object
    """
    period, created = Period.objects.get_or_create(
        family=family,
        start_date=start_date,
        defaults={
            'end_date': end_date,
            'period_type': period_type,
            'currency': family.configuration.base_currency if hasattr(family, 'configuration') else 'USD'
        }
    )
    
    # Se já existe mas precisa atualizar end_date ou period_type
    if not created:
        updated = False
        if period.end_date != end_date:
            period.end_date = end_date
            updated = True
        if period.period_type != period_type:
            period.period_type = period_type
            updated = True
        if updated:
            period.save()
    
    return period


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

    # Check if this date falls within a Period entry
    period = Period.objects.filter(
        family=family,
        start_date__lte=reference_date,
        end_date__gte=reference_date
    ).first()
    
    if period:
        # Return the period boundaries from Period table
        period_label = f"{period.start_date.strftime('%b %d')} - {period.end_date.strftime('%b %d, %Y')}"
        return period.start_date, period.end_date, period_label
    
    if not config:
        # Default to standard calendar month if no config
        start_date = reference_date.replace(day=1)
        try:
            end_date = reference_date.replace(month=reference_date.month + 1, day=1) - datetime.timedelta(days=1)
        except ValueError:
            end_date = reference_date.replace(year=reference_date.year + 1, month=1, day=1) - datetime.timedelta(days=1)
        period_label = f"{start_date.strftime('%B %Y')}"
        return start_date, end_date, period_label
    
    period_type = config.period_type
    
    if period_type == 'M':
        # Monthly Period
        starting_day = config.starting_day
        
        # Calculate period start based on starting_day
        year, month = reference_date.year, reference_date.month
        
        # If reference date is before starting_day, we're in previous month's period
        if reference_date.day < starting_day:
            if month == 1:
                month = 12
                year -= 1
            else:
                month -= 1
        
        # Determine actual starting day (handle months with fewer days)
        max_day = monthrange(year, month)[1]
        actual_start_day = min(starting_day, max_day)
        
        start_date = datetime.date(year, month, actual_start_day)
        
        # Calculate end date (day before next period starts)
        next_month = month + 1
        next_year = year
        if next_month > 12:
            next_month = 1
            next_year += 1
        
        max_day_next = monthrange(next_year, next_month)[1]
        actual_start_day_next = min(starting_day, max_day_next)
        
        end_date = datetime.date(next_year, next_month, actual_start_day_next) - datetime.timedelta(days=1)
        
        period_label = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
    
    elif period_type == 'B':
        # Bi-weekly Period (14 days)
        base_date = config.base_date
        
        # Calculate days difference from base date
        days_diff = (reference_date - base_date).days
        
        # Find the start of the current bi-weekly period
        periods_elapsed = days_diff // 14
        start_date = base_date + datetime.timedelta(days=periods_elapsed * 14)
        end_date = start_date + datetime.timedelta(days=13)
        
        period_label = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
    
    else:  # period_type == 'W'
        # Weekly Period (7 days)
        base_date = config.base_date
        
        # Calculate days difference from base date
        days_diff = (reference_date - base_date).days
        
        # Find the start of the current weekly period
        periods_elapsed = days_diff // 7
        start_date = base_date + datetime.timedelta(days=periods_elapsed * 7)
        end_date = start_date + datetime.timedelta(days=6)
        
        period_label = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
    
    return start_date, end_date, period_label


def calculate_period_for_date(family, target_date, period_type, starting_day=None, base_date=None):
    """
    Calculates which period a specific date belongs to, using given configuration.
    Used for simulating period boundaries when configuration changes.
    """
    if period_type == 'M':
        # Monthly Period
        year, month = target_date.year, target_date.month
        
        # If target date is before starting_day, we're in previous month's period
        if target_date.day < starting_day:
            if month == 1:
                month = 12
                year -= 1
            else:
                month -= 1
        
        # Determine actual starting day (handle months with fewer days)
        max_day = monthrange(year, month)[1]
        actual_start_day = min(starting_day, max_day)
        
        start_date = datetime.date(year, month, actual_start_day)
        
        # Calculate end date
        next_month = month + 1
        next_year = year
        if next_month > 12:
            next_month = 1
            next_year += 1
        
        max_day_next = monthrange(next_year, next_month)[1]
        actual_start_day_next = min(starting_day, max_day_next)
        
        end_date = datetime.date(next_year, next_month, actual_start_day_next) - datetime.timedelta(days=1)
        
    elif period_type == 'B':
        # Bi-weekly Period
        days_diff = (target_date - base_date).days
        periods_elapsed = days_diff // 14
        start_date = base_date + datetime.timedelta(days=periods_elapsed * 14)
        end_date = start_date + datetime.timedelta(days=13)
        
    else:  # Weekly
        days_diff = (target_date - base_date).days
        periods_elapsed = days_diff // 7
        start_date = base_date + datetime.timedelta(days=periods_elapsed * 7)
        end_date = start_date + datetime.timedelta(days=6)
    
    return start_date, end_date


def check_period_change_impact(family, new_period_type, new_starting_day=None, new_base_date=None):
    """
    Analyzes the impact of changing period settings.
    
    Returns a dict with:
    - 'requires_close': bool - if current period needs to be closed/adjusted
    - 'current_period': tuple - (start_date, end_date, label) with OLD config
    - 'new_current_period': tuple - (start_date, end_date, label) with NEW config
    - 'adjustment_period': tuple or None - (start_date, end_date) for adjustment period if needed
    - 'message': str - detailed warning message for user
    """
    config = family.configuration
    today = timezone.localdate()
    
    old_type = config.period_type
    old_starting_day = config.starting_day
    old_base_date = config.base_date
    
    # Get current period with OLD settings
    current_start, current_end, current_label = get_current_period_dates(family, None)
    
    # Calculate where we should be with NEW settings
    if new_period_type == 'M':
        new_start, new_end = calculate_period_for_date(
            family, today, new_period_type, 
            starting_day=new_starting_day or old_starting_day
        )
    else:
        new_start, new_end = calculate_period_for_date(
            family, today, new_period_type,
            base_date=new_base_date or old_base_date
        )
    
    new_label = f"{new_start.strftime('%b %d')} - {new_end.strftime('%b %d, %Y')}"
    
    requires_close = False
    adjustment_period = None
    message = ""
    
    # CASE 1: Same period type, changing starting day (Monthly only)
    if old_type == new_period_type == 'M' and new_starting_day != old_starting_day:
        # Check if new starting day would create a split
        if new_start != current_start or new_end != current_end:
            requires_close = True
            
            if new_starting_day < old_starting_day:
                message = f"Moving starting day from {old_starting_day} to {new_starting_day} will make the current period {(current_end - current_start).days + 1} days long (ending {current_end.strftime('%b %d')}). The next period will start on {new_start.strftime('%b %d')} with the new schedule."
            else:
                message = f"Moving starting day from {old_starting_day} to {new_starting_day} will make the current period {(current_end - current_start).days + 1} days long (ending {current_end.strftime('%b %d')}). The next period will start on {new_start.strftime('%b %d')} with the new schedule."
    
    # CASE 2: Changing base date (Bi-weekly or Weekly)
    elif old_type == new_period_type and old_type in ['B', 'W']:
        if new_base_date and new_base_date != old_base_date:
            requires_close = True
            
            # Calculate where the new period boundaries would be with new base date
            if new_start > current_start:
                # New period would start AFTER current period started
                # Need to create an adjustment period
                adjustment_period = (current_start, new_start - datetime.timedelta(days=1))
                message = f"Changing base date will create an adjustment period from {adjustment_period[0].strftime('%b %d')} to {adjustment_period[1].strftime('%b %d')} ({(adjustment_period[1] - adjustment_period[0]).days + 1} days). The new {dict(config.PERIOD_TYPES)[new_period_type].lower()} cycle will start on {new_start.strftime('%b %d, %Y')}."
            else:
                # New period would have started before current period
                message = f"Changing base date will adjust your current period. The period will be recalculated to align with the new base date starting {new_start.strftime('%b %d, %Y')}."
    
    # CASE 3: Changing period type
    elif old_type != new_period_type:
        requires_close = True
        
        # Determine if new period would have already started
        if new_start > current_start and new_start <= today:
            # New period should have started already
            adjustment_period = (current_start, new_start - datetime.timedelta(days=1))
            adj_days = (adjustment_period[1] - adjustment_period[0]).days + 1
            
            message = f"Changing from {dict(config.PERIOD_TYPES)[old_type]} to {dict(config.PERIOD_TYPES)[new_period_type]} will create an adjustment period of {adj_days} days (from {adjustment_period[0].strftime('%b %d')} to {adjustment_period[1].strftime('%b %d')}). Your new {dict(config.PERIOD_TYPES)[new_period_type].lower()} cycle will start on {new_start.strftime('%b %d, %Y')}."
        else:
            message = f"Changing from {dict(config.PERIOD_TYPES)[old_type]} to {dict(config.PERIOD_TYPES)[new_period_type]} will adjust the current period. The new {dict(config.PERIOD_TYPES)[new_period_type].lower()} cycle starts on {new_start.strftime('%b %d, %Y')}."
    
    return {
        'requires_close': requires_close,
        'current_period': (current_start, current_end, current_label),
        'new_current_period': (new_start, new_end, new_label),
        'adjustment_period': adjustment_period,
        'message': message
    }


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
        copied = copy_flow_groups_to_new_period(
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
            adj_end = new_start - datetime.timedelta(days=1)
            
            period = ensure_period_exists(family, current_start, adj_end, old_config['period_type'])
            period.currency = current_currency
            period.save()
            results['periods_created'].append(period)
    
    # Ensure Period exists for the NEW current period
    new_period = ensure_period_exists(family, new_start, new_end, new_config['period_type'])
    new_period.currency = current_currency
    new_period.save()
    
    # Copy FlowGroups to the NEW current period
    copied = copy_flow_groups_to_new_period(
        family,
        current_start,  # Source period
        new_start,      # New period start
        new_end         # New period end
    )
    results['flow_groups_copied'] += copied
    
    return results


def copy_flow_groups_to_new_period(family, old_period_start, new_period_start, new_period_end):
    """
    Copies FlowGroups from old period to new period.
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


def get_available_periods(family):
    """
    Returns list of available periods for selection.
    Uses Period table to show all existing periods + current period + one empty period before.
    """
    config = getattr(family, 'configuration', None)
    if not config:
        return []
    
    today = timezone.localdate()
    periods = []
    
    # Get all Period entries
    period_entries = Period.objects.filter(family=family).order_by('-start_date')
    
    # Get current period
    current_start, current_end, current_label = get_current_period_dates(family, None)
    
    # Add current period (always show)
    periods.append({
        'label': current_label,
        'value': current_start.strftime('%Y-%m-%d'),
        'start_date': current_start,
        'end_date': current_end,
        'is_current': True,
        'has_data': FlowGroup.objects.filter(family=family, period_start_date=current_start).exists()
    })
    
    # Add periods from Period table
    for period in period_entries:
        if period.start_date != current_start:
            _, period_end, period_label = get_current_period_dates(family, period.start_date.strftime('%Y-%m-%d'))
            periods.append({
                'label': period_label,
                'value': period.start_date.strftime('%Y-%m-%d'),
                'start_date': period.start_date,
                'end_date': period_end,
                'is_current': False,
                'has_data': FlowGroup.objects.filter(family=family, period_start_date=period.start_date).exists()
            })
    
    # Add one empty period before the oldest period
    if period_entries:
        import datetime
        
        oldest_period = min([p.start_date for p in period_entries] + [current_start])
        
        # Calculate previous period based on period_type
        if config.period_type == 'M':
            # Monthly: go back one month
            prev_month_ref = oldest_period - relativedelta(months=1)
        elif config.period_type == 'B':
            # Bi-weekly: go back 14 days
            prev_month_ref = oldest_period - datetime.timedelta(days=14)
        else:  # Weekly
            # Weekly: go back 7 days
            prev_month_ref = oldest_period - datetime.timedelta(days=7)
        
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
    else:
        # No periods exist yet - add one previous empty period
        import datetime
        
        if config.period_type == 'M':
            # Monthly: go back one month
            prev_month_ref = today - relativedelta(months=1)
        elif config.period_type == 'B':
            # Bi-weekly: go back 14 days
            prev_month_ref = today - datetime.timedelta(days=14)
        else:  # Weekly
            # Weekly: go back 7 days
            prev_month_ref = today - datetime.timedelta(days=7)
        
        prev_start, prev_end, prev_label = get_current_period_dates(family, prev_month_ref.strftime('%Y-%m-%d'))
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
        role_history = FamilyMemberRoleHistory.objects.filter(
            member=member,
            period_start_date__lte=period_start_date
        ).order_by('-period_start_date').first()
        
        if role_history:
            return role_history.role
    except:
        pass
    
    return member.role


def save_role_history_if_changed(member, new_role, period_start_date):
    """
    Saves role history if the role changed.
    Should be called when updating a member's role.
    """
    current_role = get_member_role_for_period(member, period_start_date)
    
    if current_role != new_role:
        FamilyMemberRoleHistory.objects.update_or_create(
            member=member,
            period_start_date=period_start_date,
            defaults={'role': new_role}
        )
        
        member.role = new_role
        member.save()


def copy_previous_period_data(family, from_period_start, to_period_start, to_period_end):
    """
    Copies FlowGroups and their structure from one period to another.
    Does NOT copy transactions, only the group structure.
    """
    return copy_flow_groups_to_new_period(family, from_period_start, to_period_start, to_period_end)


def current_period_has_data(family):
    """
    Checks if the current period has any transactions.
    """
    current_start, current_end, _ = get_current_period_dates(family, None)
    
    return Transaction.objects.filter(
        flow_group__family=family,
        date__range=(current_start, current_end)
    ).exists()


def close_current_period(family):
    """
    Creates/updates a Period record for the current period.
    Should be called when period settings are about to change.
    Returns the Period object.
    """
    config = family.configuration
    current_start, current_end, _ = get_current_period_dates(family, None)
    
    period = ensure_period_exists(
        family=family,
        start_date=current_start,
        end_date=current_end,
        period_type=config.period_type
    )
    
    # Ensure currency is set
    if not period.currency or period.currency != config.base_currency:
        period.currency = config.base_currency
        period.save()
    
    return period
