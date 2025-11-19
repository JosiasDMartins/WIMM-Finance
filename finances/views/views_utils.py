import json
from decimal import Decimal
from django.utils import translation
from django.db.models import Sum, Q
from django.utils import timezone
from babel.numbers import get_group_symbol, get_currency_symbol as get_currency_symbol_babel

# Relative imports from the app (.. moves up one level, from /views/ to /finances/)
from ..models import (
    FamilyMember, FlowGroup, Transaction, SystemVersion,
    FLOW_TYPE_INCOME, FLOW_TYPE_EXPENSE
)
from ..utils import (
    get_available_periods,
    get_period_currency
)

#Import global version (only files)
from ..context_processors import VERSION


def get_thousand_separator():
    """
    Returns the thousands separator for the active language.
    """
    lang = translation.get_language()
    locale_para_babel = translation.to_locale(lang)
    return get_group_symbol(locale_para_babel)


def get_currency_symbol(currency_code):
    """
    Get the correct currency symbol using Django's active locale.
    """
    lang = translation.get_language()
    locale_para_babel = translation.to_locale(lang)
    return get_currency_symbol_babel(currency_code, locale=locale_para_babel)


def get_family_context(user):
    """Retrieves the Family and Member context for the logged-in user.."""
    try:
        family_member = FamilyMember.objects.select_related('family').get(user=user)
        family = family_member.family
        all_family_members = FamilyMember.objects.filter(family=family).select_related('user').order_by('user__username')
        return family, family_member, all_family_members
    except FamilyMember.DoesNotExist:
        return None, None, []


def get_default_income_flow_group(family, user, period_start_date):
    """Retrieves or creates the default income FlowGroup for the family and period."""
    from ..utils import ensure_period_exists, get_current_period_dates
    from moneyed import Money

    currency = get_period_currency(family, period_start_date)
    
    income_group, created = FlowGroup.objects.get_or_create(
        family=family,
        group_type=FLOW_TYPE_INCOME,
        period_start_date=period_start_date,
        defaults={
            'name': 'Income (Default)', 
            'budgeted_amount': Money(0, currency),
            'owner': user
        }
    )
    
    if created:
        config = getattr(family, 'configuration', None)
        if config:
            _, end_date, _ = get_current_period_dates(family, period_start_date.strftime('%Y-%m-%d'))
            ensure_period_exists(family, period_start_date, end_date, config.period_type)
    
    return income_group


def can_access_flow_group(flow_group, family_member):
    """Checks if a family member can access a specific FlowGroup."""
    if flow_group.owner == family_member.user:
        return True
    
    if family_member.role == 'ADMIN':
        return True
    
    if flow_group.group_type == FLOW_TYPE_INCOME:
        return True
    
    if family_member.role == 'PARENT':
        if flow_group.is_shared:
            if flow_group.assigned_members.filter(id=family_member.id).exists():
                return True
        if flow_group.is_kids_group:
            return True
    
    if family_member.role == 'CHILD':
        if flow_group.is_kids_group and family_member in flow_group.assigned_children.all():
            return True
    
    return False


def get_visible_flow_groups_for_dashboard(family, family_member, period_start_date, group_type_filter=None):
    """
    Returns FlowGroups visible on the dashboard.
    (accessible_groups, display_only_groups)
    """
    base_query = FlowGroup.objects.filter(
        family=family,
        period_start_date=period_start_date
    )
    
    if group_type_filter:
        base_query = base_query.filter(group_type__in=group_type_filter)
    
    if family_member.role == 'CHILD':
        accessible_groups = base_query.filter(
            Q(is_kids_group=True, assigned_children=family_member)
        ).distinct()
        display_only_groups = FlowGroup.objects.none()
    else:
        all_groups = base_query.all()
        accessible_ids = []
        display_only_ids = []
        
        for group in all_groups:
            if can_access_flow_group(group, family_member):
                accessible_ids.append(group.id)
            else:
                display_only_ids.append(group.id)
        
        accessible_groups = base_query.filter(id__in=accessible_ids)
        display_only_groups = base_query.filter(id__in=display_only_ids)
    
    return accessible_groups, display_only_groups


def get_visible_flow_groups(family, family_member, period_start_date, group_type_filter=None):
    """Returns FlowGroups visible for editing/access."""
    base_query = FlowGroup.objects.filter(
        family=family,
        period_start_date=period_start_date
    )
    
    if group_type_filter:
        base_query = base_query.filter(group_type__in=group_type_filter)
    
    if family_member.role == 'CHILD':
        visible_groups = base_query.filter(
            Q(is_kids_group=True, assigned_children=family_member)
        )
    elif family_member.role == 'ADMIN':
        visible_groups = base_query.all()
    else:
        visible_groups = base_query.filter(
            Q(owner=family_member.user) |
            Q(is_shared=True, assigned_members=family_member) |
            Q(is_kids_group=True)
        )
    
    return visible_groups.distinct()


def get_base_template_context(family, query_period, start_date):
    """Retrieves the base context for the template (period selector, version)."""
    available_periods = get_available_periods(family)
    
    current_period_label = None
    current_period_value = query_period if query_period else start_date.strftime("%Y-%m-%d")
    
    for period in available_periods:
        if period['value'] == current_period_value:
            period['is_current'] = True
            current_period_label = period['label']
        else:
            period['is_current'] = False
    
    if not current_period_label and available_periods:
        available_periods[0]['is_current'] = True
        current_period_label = available_periods[0]['label']
    
    
    return {
        'available_periods': available_periods,
        'current_period_label': current_period_label,
        'selected_period': current_period_value,
        #'app_version': VERSION,
    }


def get_default_date_for_period(start_date, end_date):
    """Returns the default date for data entry within the period."""
    today = timezone.localdate()
    
    if start_date <= today <= end_date:
        return today
    else:
        return start_date


def get_periods_history(family, current_period_start):
    """Returns the historical data for the last 12 periods, which can be used for the chart."""
    available_periods = get_available_periods(family)

    periods_to_show = []
    savings_values = []

    for period in available_periods[:24]:
        period_start = period['start_date']
        period_end = period['end_date']

        has_data = Transaction.objects.filter(
            flow_group__family=family,
            date__range=(period_start, period_end)
        ).exists()

        if not has_data:
            continue

        total_expenses = Transaction.objects.filter(
            flow_group__family=family,
            flow_group__group_type__in=FLOW_TYPE_EXPENSE,
            date__range=(period_start, period_end),
            realized=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        total_income = Transaction.objects.filter(
            flow_group__family=family,
            flow_group__group_type=FLOW_TYPE_INCOME,
            date__range=(period_start, period_end),
            realized=True,
            is_child_manual_income=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        kids_realized = FlowGroup.objects.filter(
            family=family,
            period_start_date=period_start,
            is_kids_group=True,
            realized=True
        ).aggregate(total=Sum('budgeted_amount'))['total'] or Decimal('0.00')

        total_expenses += kids_realized

        total_expenses_float = float(total_expenses.amount) if hasattr(total_expenses, 'amount') else float(total_expenses)
        total_income_float = float(total_income.amount) if hasattr(total_income, 'amount') else float(total_income)

        commitment_pct = 0
        if total_income_float > 0:
            commitment_pct = (total_expenses_float / total_income_float * 100)

        if commitment_pct >= 98:
            bar_color = 'rgb(239, 68, 68)'
        elif commitment_pct >= 90:
            bar_color = 'rgb(249, 115, 22)'
        else:
            bar_color = 'rgb(134, 239, 172)'

        savings = total_income_float - total_expenses_float
        savings_values.append(savings)

        periods_to_show.append({
            'label': period['label'],
            'value': total_expenses_float,
            'color': bar_color,
            'savings': savings
        })

        if len(periods_to_show) >= 12:
            break

    periods_to_show.reverse()
    savings_values.reverse()

    avg_savings = sum(savings_values) / len(savings_values) if savings_values else 0

    trend = 'stable'
    if len(periods_to_show) >= 6:
        half_point = len(periods_to_show) // 2
        first_half_avg = sum(p['value'] for p in periods_to_show[:half_point]) / half_point
        second_half_avg = sum(p['value'] for p in periods_to_show[half_point:]) / (len(periods_to_show) - half_point)

        if second_half_avg > first_half_avg * 1.05:
            trend = 'up'
        elif second_half_avg < first_half_avg * 0.95:
            trend = 'down'

    return {
        'labels': [p['label'] for p in periods_to_show],
        'values': [p['value'] for p in periods_to_show],
        'colors': [p['color'] for p in periods_to_show],
        'avg_savings': avg_savings,
        'trend': trend
    }


def get_year_to_date_metrics(family, current_period_end):
    """
    Returns year-to-date metrics from January 1 to the current selected period.
    Returns realized values for: total savings, total investments, total income.
    """
    from datetime import date

    # Get the year from the current period
    current_year = current_period_end.year
    year_start = date(current_year, 1, 1)

    # Total Income (realized only, excluding child manual income)
    total_income = Transaction.objects.filter(
        flow_group__family=family,
        flow_group__group_type=FLOW_TYPE_INCOME,
        date__range=(year_start, current_period_end),
        realized=True,
        is_child_manual_income=False
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    total_income_float = float(total_income.amount) if hasattr(total_income, 'amount') else float(total_income)

    # Total Expenses (realized only)
    total_expenses = Transaction.objects.filter(
        flow_group__family=family,
        flow_group__group_type__in=FLOW_TYPE_EXPENSE,
        flow_group__is_investment=False,
        date__range=(year_start, current_period_end),
        realized=True
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Add kids groups realized budgets (exclude investment kids groups)
    kids_realized = FlowGroup.objects.filter(
        family=family,
        period_start_date__range=(year_start, current_period_end),
        is_kids_group=True,
        is_investment=False,
        realized=True
    ).aggregate(total=Sum('budgeted_amount'))['total'] or Decimal('0.00')

    total_expenses += kids_realized
    total_expenses_float = float(total_expenses.amount) if hasattr(total_expenses, 'amount') else float(total_expenses)

    # Total Investments (realized only)
    total_investments = Transaction.objects.filter(
        flow_group__family=family,
        flow_group__group_type__in=FLOW_TYPE_EXPENSE,
        flow_group__is_investment=True,
        date__range=(year_start, current_period_end),
        realized=True
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Add investment kids groups realized budgets
    kids_investment_realized = FlowGroup.objects.filter(
        family=family,
        period_start_date__range=(year_start, current_period_end),
        is_kids_group=True,
        is_investment=True,
        realized=True
    ).aggregate(total=Sum('budgeted_amount'))['total'] or Decimal('0.00')

    total_investments += kids_investment_realized
    total_investments_float = float(total_investments.amount) if hasattr(total_investments, 'amount') else float(total_investments)

    # Total Savings = Income - Expenses - Investments
    total_savings = total_income_float - total_expenses_float - total_investments_float

    return {
        'ytd_savings': total_savings,
        'ytd_investments': total_investments_float,
        'ytd_income': total_income_float,
    }