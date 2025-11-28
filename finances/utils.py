# finances/utils.py

import datetime
import logging
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.conf import settings
from dateutil.relativedelta import relativedelta
from calendar import monthrange
from .models import Transaction, FlowGroup, FamilyMemberRoleHistory, Period

logger = logging.getLogger(__name__)


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


def check_period_change_impact(family, new_period_type, new_starting_day=None, new_base_date=None,
                               old_period_type=None, old_starting_day=None, old_base_date=None):
    """
    Analyzes the impact of changing period settings.

    Args:
        family: Family object
        new_period_type: The new period type ('M', 'B', or 'W')
        new_starting_day: Optional new starting day (for Monthly)
        new_base_date: Optional new base date (for Bi-weekly/Weekly)
        old_period_type: Optional old period type (if provided, uses this instead of reading from DB)
        old_starting_day: Optional old starting day (if provided, uses this instead of reading from DB)
        old_base_date: Optional old base date (if provided, uses this instead of reading from DB)

    Returns a dict with:
    - 'requires_close': bool - if current period needs to be closed/adjusted
    - 'current_period': tuple - (start_date, end_date, label) with OLD config
    - 'new_current_period': tuple - (start_date, end_date, label) with NEW config
    - 'adjustment_period': tuple or None - (start_date, end_date) for adjustment period if needed
    - 'message': str - detailed warning message for user
    """
    config = family.configuration
    today = timezone.localdate()

    if settings.DEBUG:
        logger.debug("[check_period_change_impact] Called with:")
        logger.debug(f"  old_period_type={old_period_type}, new_period_type={new_period_type}")
        logger.debug(f"  old_starting_day={old_starting_day}, new_starting_day={new_starting_day}")
        logger.debug(f"  old_base_date={old_base_date}, new_base_date={new_base_date}")

    # Use provided old values if given, otherwise read from database
    if old_period_type is not None:
        old_type = old_period_type
    else:
        old_type = config.period_type

        # Defensive check: Ensure old_type is a valid string, not corrupted data
        if not isinstance(old_type, str) or old_type not in ['M', 'B', 'W']:
            # Data corruption detected - fix it by defaulting to Monthly
            old_type = 'M'
            config.period_type = 'M'
            config.save()

    # Use provided old values or read from config
    if old_starting_day is None:
        old_starting_day = config.starting_day

    if old_base_date is None:
        old_base_date = config.base_date
    
    # Get current period with OLD settings
    current_start, current_end, current_label = get_current_period_dates(family, None)

    # Calculate where we should be with NEW settings
    # When changing period types, we need to find the NEXT period that should start
    if new_period_type == 'M':
        # For Monthly: calculate period containing today first
        temp_start, temp_end = calculate_period_for_date(
            family, today, new_period_type,
            starting_day=new_starting_day or old_starting_day
        )

        # If changing period type and temp_start is before current_start,
        # we need the NEXT period, not the one containing today
        if old_type != new_period_type and temp_start < current_start:
            # Calculate next period
            next_month_date = temp_end + datetime.timedelta(days=1)
            new_start, new_end = calculate_period_for_date(
                family, next_month_date, new_period_type,
                starting_day=new_starting_day or old_starting_day
            )
            if settings.DEBUG:
                logger.debug(f"[DEBUG PERIOD]   temp_start < current_start, using NEXT period: {new_start} to {new_end}")
        else:
            new_start, new_end = temp_start, temp_end
    else:
        # For Bi-weekly/Weekly
        temp_start, temp_end = calculate_period_for_date(
            family, today, new_period_type,
            base_date=new_base_date or old_base_date
        )

        # If changing period type and temp_start is before current_start,
        # we need the NEXT period
        if old_type != new_period_type and temp_start < current_start:
            next_period_date = temp_end + datetime.timedelta(days=1)
            new_start, new_end = calculate_period_for_date(
                family, next_period_date, new_period_type,
                base_date=new_base_date or old_base_date
            )
            if settings.DEBUG:
                logger.debug(f"[DEBUG PERIOD]   temp_start < current_start, using NEXT period: {new_start} to {new_end}")
        else:
            new_start, new_end = temp_start, temp_end

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
                message = _("Moving starting day from %(old_day)s to %(new_day)s will make the current period %(days)s days long (ending %(end_date)s). The next period will start on %(start_date)s with the new schedule.") % {
                    'old_day': old_starting_day,
                    'new_day': new_starting_day,
                    'days': (current_end - current_start).days + 1,
                    'end_date': current_end.strftime('%b %d'),
                    'start_date': new_start.strftime('%b %d')
                }
            else:
                message = _("Moving starting day from %(old_day)s to %(new_day)s will make the current period %(days)s days long (ending %(end_date)s). The next period will start on %(start_date)s with the new schedule.") % {
                    'old_day': old_starting_day,
                    'new_day': new_starting_day,
                    'days': (current_end - current_start).days + 1,
                    'end_date': current_end.strftime('%b %d'),
                    'start_date': new_start.strftime('%b %d')
                }

    # CASE 2: Changing base date (Bi-weekly or Weekly)
    elif old_type == new_period_type and old_type in ['B', 'W']:
        if new_base_date and new_base_date != old_base_date:
            requires_close = True

            # Calculate where the new period boundaries would be with new base date
            if new_start > current_start:
                # New period would start AFTER current period started
                # Need to create an adjustment period
                adjustment_period = (current_start, new_start - datetime.timedelta(days=1))
                message = _("Changing base date will create an adjustment period from %(adj_start)s to %(adj_end)s (%(adj_days)s days). The new %(period_type)s cycle will start on %(start_date)s.") % {
                    'adj_start': adjustment_period[0].strftime('%b %d'),
                    'adj_end': adjustment_period[1].strftime('%b %d'),
                    'adj_days': (adjustment_period[1] - adjustment_period[0]).days + 1,
                    'period_type': dict(config.PERIOD_TYPES)[new_period_type].lower(),
                    'start_date': new_start.strftime('%b %d, %Y')
                }
            else:
                # New period would have started before current period
                message = _("Changing base date will adjust your current period. The period will be recalculated to align with the new base date starting %(start_date)s.") % {
                    'start_date': new_start.strftime('%b %d, %Y')
                }

    # CASE 3: Changing period type
    elif old_type != new_period_type:
        requires_close = True

        if settings.DEBUG:
            logger.debug("[DEBUG PERIOD] [check_period_change_impact] CASE 3: Period type change detected")
            logger.debug(f"[DEBUG PERIOD]   old_type={old_type}, new_period_type={new_period_type}")

        # Define period hierarchy: W < B < M (Weekly < Bi-weekly < Monthly)
        period_order = {'W': 1, 'B': 2, 'M': 3}

        # Check if moving from smaller to larger period
        is_moving_to_larger = period_order[new_period_type] > period_order[old_type]

        if settings.DEBUG:
            logger.debug(f"[DEBUG PERIOD]   is_moving_to_larger={is_moving_to_larger}")
            logger.debug(f"[DEBUG PERIOD]   current_start={current_start}, current_end={current_end}")
            logger.debug(f"[DEBUG PERIOD]   new_start={new_start}, new_end={new_end}")
            logger.debug(f"[DEBUG PERIOD]   today={today}")

        if is_moving_to_larger:
            # Moving from smaller to larger period (W→B, W→M, B→M)
            # Strategy: Close current period early and create adjustment period
            # The adjustment period replaces the current period, ending the day before new period starts

            if new_start <= current_start:
                # New period would have started before or at current period start
                # Use new period boundaries directly, no adjustment needed
                message = _("Changing from %(old_type)s to %(new_type)s will adjust the current period. The new %(new_type_lower)s cycle starts on %(start_date)s.") % {
                    'old_type': dict(config.PERIOD_TYPES)[old_type],
                    'new_type': dict(config.PERIOD_TYPES)[new_period_type],
                    'new_type_lower': dict(config.PERIOD_TYPES)[new_period_type].lower(),
                    'start_date': new_start.strftime('%b %d, %Y')
                }
            else:
                # New period start is after current period start
                # Create adjustment period: from current start to day before new period starts
                # This closes the current period early to align with new period type
                adjustment_period = (current_start, new_start - datetime.timedelta(days=1))
                adj_days = (adjustment_period[1] - adjustment_period[0]).days + 1

                if settings.DEBUG:
                    logger.debug(f"[DEBUG PERIOD]   Creating adjustment period: {adjustment_period[0]} to {adjustment_period[1]} ({adj_days} days)")

                message = _("Changing from %(old_type)s to %(new_type)s will close the current period early, creating an adjustment period of %(adj_days)s days (from %(adj_start)s to %(adj_end)s). Your new %(new_type_lower)s cycle will start on %(start_date)s.") % {
                    'old_type': dict(config.PERIOD_TYPES)[old_type],
                    'new_type': dict(config.PERIOD_TYPES)[new_period_type],
                    'adj_days': adj_days,
                    'adj_start': adjustment_period[0].strftime('%b %d'),
                    'adj_end': adjustment_period[1].strftime('%b %d'),
                    'new_type_lower': dict(config.PERIOD_TYPES)[new_period_type].lower(),
                    'start_date': new_start.strftime('%b %d, %Y')
                }
        else:
            # Moving from larger to smaller period (M→B, M→W, B→W)
            # Strategy: Close current period and create adjustment if needed

            if new_start > current_start and new_start <= today:
                # New period should have started already
                adjustment_period = (current_start, new_start - datetime.timedelta(days=1))
                adj_days = (adjustment_period[1] - adjustment_period[0]).days + 1

                message = _("Changing from %(old_type)s to %(new_type)s will create an adjustment period of %(adj_days)s days (from %(adj_start)s to %(adj_end)s). Your new %(new_type_lower)s cycle will start on %(start_date)s.") % {
                    'old_type': dict(config.PERIOD_TYPES)[old_type],
                    'new_type': dict(config.PERIOD_TYPES)[new_period_type],
                    'adj_days': adj_days,
                    'adj_start': adjustment_period[0].strftime('%b %d'),
                    'adj_end': adjustment_period[1].strftime('%b %d'),
                    'new_type_lower': dict(config.PERIOD_TYPES)[new_period_type].lower(),
                    'start_date': new_start.strftime('%b %d, %Y')
                }
            else:
                message = _("Changing from %(old_type)s to %(new_type)s will adjust the current period. The new %(new_type_lower)s cycle starts on %(start_date)s.") % {
                    'old_type': dict(config.PERIOD_TYPES)[old_type],
                    'new_type': dict(config.PERIOD_TYPES)[new_period_type],
                    'new_type_lower': dict(config.PERIOD_TYPES)[new_period_type].lower(),
                    'start_date': new_start.strftime('%b %d, %Y')
                }

    result = {
        'requires_close': requires_close,
        'current_period': (current_start, current_end, current_label),
        'new_current_period': (new_start, new_end, new_label),
        'adjustment_period': adjustment_period,
        'message': message
    }

    if settings.DEBUG:
        logger.debug("[DEBUG PERIOD] [check_period_change_impact] Returning:")
        logger.debug(f"[DEBUG PERIOD]   requires_close={requires_close}")
        logger.debug(f"[DEBUG PERIOD]   adjustment_period={adjustment_period}")
        logger.debug(f"[DEBUG PERIOD]   message={message}")

    return result


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
    copied = copy_previous_period_data(
        family,
        current_start,  # Source period
        new_start,      # New period start
        new_end         # New period end
    )
    results['flow_groups_copied'] += copied
    
    return results


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
    Only shows periods that exist in the Period table.
    No automatic creation of retroactive periods.
    """
    config = getattr(family, 'configuration', None)
    if not config:
        return []

    today = timezone.localdate()
    periods = []

    # Get all Period entries from database
    period_entries = Period.objects.filter(family=family).order_by('-start_date')

    # Get current period date range
    current_start, current_end, current_label = get_current_period_dates(family, None)

    # Build list of available periods from Period table
    for period in period_entries:
        # Calculate period label using get_current_period_dates
        _, period_end, period_label = get_current_period_dates(family, period.start_date.strftime('%Y-%m-%d'))

        is_current = (period.start_date == current_start)

        periods.append({
            'label': period_label,
            'value': period.start_date.strftime('%Y-%m-%d'),
            'start_date': period.start_date,
            'end_date': period_end,
            'is_current': is_current,
            'has_data': FlowGroup.objects.filter(family=family, period_start_date=period.start_date).exists()
        })

    # If no periods exist at all, return empty list
    # User must explicitly create periods via the UI

    # Sort by start_date descending (most recent first)
    periods.sort(key=lambda x: x['start_date'], reverse=True)

    return periods


def user_can_access_flow_group(user, flow_group):
    """
    Checks if the user has access to the FlowGroup.
    This is a wrapper for can_access_flow_group that accepts User instead of FamilyMember.
    Uses the complete access logic including role checks, shared groups, and kids groups.
    """
    from .views.views_utils import can_access_flow_group

    try:
        member = user.memberships.get(family=flow_group.family)
        return can_access_flow_group(flow_group, member)
    except FamilyMember.DoesNotExist:
        return False
    except Exception:
        # Catch any other unexpected errors
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
    except FamilyMemberRoleHistory.DoesNotExist:
        pass
    except Exception:
        # Unexpected error - fallback to current role
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
