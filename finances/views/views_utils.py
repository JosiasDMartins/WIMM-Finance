import json
from decimal import Decimal
from django.utils import translation
from django.db.models import Sum, Q
from django.utils import timezone
from babel.numbers import get_group_symbol, get_decimal_symbol, get_currency_symbol as get_currency_symbol_babel

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


def _get_babel_locale():
    """
    Returns the Babel locale string for the current active Django language.
    This is a private helper function used by locale-dependent formatting functions.
    """
    lang = translation.get_language()
    return translation.to_locale(lang)


def get_thousand_separator():
    """
    Returns the thousands separator for the active language.
    """
    return get_group_symbol(_get_babel_locale())


def get_decimal_separator():
    """
    Returns the decimal separator for the active language.
    """
    return get_decimal_symbol(_get_babel_locale())


def get_currency_symbol(currency_code):
    """
    Get the correct currency symbol using Django's active locale.
    """
    return get_currency_symbol_babel(currency_code, locale=_get_babel_locale())


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
            _unused1, end_date, _unused2 = get_current_period_dates(family, period_start_date.strftime('%Y-%m-%d'))
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


def get_year_to_date_metrics(family, current_period_end, current_member=None):
    """
    Returns year-to-date metrics from January 1 to the current selected period.
    Returns realized values for: total savings, total investments, total income.

    For CHILD users: calculates only their personal metrics (their groups and manual income)
    For ADMIN/PARENT users: calculates family-wide metrics
    """
    from datetime import date

    # Get the year from the current period
    current_year = current_period_end.year
    year_start = date(current_year, 1, 1)

    # Check if user is a Child
    is_child = current_member and current_member.role == 'CHILD'

    if is_child:
        # CHILD: Calculate only personal metrics

        # Income = Kids groups assigned to them + manual income they created
        kids_income = FlowGroup.objects.filter(
            family=family,
            period_start_date__range=(year_start, current_period_end),
            is_kids_group=True,
            is_investment=False,
            realized=True,
            assigned_children=current_member
        ).aggregate(total=Sum('budgeted_amount'))['total'] or Decimal('0.00')

        manual_income = Transaction.objects.filter(
            flow_group__family=family,
            flow_group__group_type=FLOW_TYPE_INCOME,
            date__range=(year_start, current_period_end),
            realized=True,
            is_child_manual_income=True,
            member=current_member
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        total_income = kids_income + manual_income
        total_income_float = float(total_income.amount) if hasattr(total_income, 'amount') else float(total_income)

        # Expenses = Only their own expense transactions
        total_expenses = Transaction.objects.filter(
            flow_group__family=family,
            flow_group__group_type__in=FLOW_TYPE_EXPENSE,
            flow_group__is_investment=False,
            date__range=(year_start, current_period_end),
            realized=True,
            is_child_expense=True,
            member=current_member
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        total_expenses_float = float(total_expenses.amount) if hasattr(total_expenses, 'amount') else float(total_expenses)

        # Investments = Only their own investment transactions
        total_investments = Transaction.objects.filter(
            flow_group__family=family,
            flow_group__group_type__in=FLOW_TYPE_EXPENSE,
            flow_group__is_investment=True,
            date__range=(year_start, current_period_end),
            realized=True,
            member=current_member
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # Add investment kids groups assigned to them
        kids_investment_income = FlowGroup.objects.filter(
            family=family,
            period_start_date__range=(year_start, current_period_end),
            is_kids_group=True,
            is_investment=True,
            realized=True,
            assigned_children=current_member
        ).aggregate(total=Sum('budgeted_amount'))['total'] or Decimal('0.00')

        total_investments += kids_investment_income
        total_investments_float = float(total_investments.amount) if hasattr(total_investments, 'amount') else float(total_investments)
    else:
        # ADMIN/PARENT: Calculate family-wide metrics (original logic)

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


def get_balance_summary(family, current_member, family_members, start_date, end_date):
    """
    Calculate balance summary (income, expense, result) for a given period.
    This function centralizes the logic used in the dashboard.

    Returns a dictionary containing:
    - 'summary_totals': Dict with final calculated totals.
    - 'recent_income_transactions': QuerySet of income transactions for the period.
    - 'income_flow_group_id': ID of the default income group.
    - 'kids_income_entries': For CHILD view, list of their income from kids groups.
    - 'children_manual_income': For PARENT/ADMIN view, dict of manual income per child.
    - 'budgeted_expense': Total budgeted expense for the period.
    - 'realized_expense': Total realized expense for the period.
    """
    from decimal import Decimal, ROUND_DOWN
    from django.db.models import Sum, Q
    from ..models import FlowGroup, Transaction, FLOW_TYPE_INCOME, FLOW_TYPE_EXPENSE
    from ..utils import get_member_role_for_period

    member_role_for_period = get_member_role_for_period(current_member, start_date)

    # Get expense groups and calculate budgeted_expense
    accessible_expense_groups, display_only_expense_groups = get_visible_flow_groups_for_dashboard(
        family, current_member, start_date, group_type_filter=FLOW_TYPE_EXPENSE
    )

    # Sum ALL transactions for FlowGroups, regardless of transaction date
    # The FlowGroup's period_start_date determines which period the transaction belongs to
    accessible_expense_groups_annotated = accessible_expense_groups.annotate(
        total_estimated=Sum('transactions__amount')
    )
    display_only_expense_groups_annotated = display_only_expense_groups.annotate(
        total_estimated=Sum('transactions__amount')
    )

    budgeted_expense = Decimal('0.00')

    for group in accessible_expense_groups_annotated:
        total_estimated = Decimal(str(group.total_estimated.amount)) if hasattr(group.total_estimated, 'amount') else (group.total_estimated or Decimal('0.00'))
        budgeted_amt = Decimal(str(group.budgeted_amount.amount)) if hasattr(group.budgeted_amount, 'amount') else Decimal(str(group.budgeted_amount))
        effective_budget = total_estimated if total_estimated > budgeted_amt else budgeted_amt

        is_child_own_group = False
        if group.owner:
            owner_member = family_members.filter(user=group.owner).first()
            if owner_member and owner_member.role == 'CHILD':
                is_child_own_group = True

        if member_role_for_period == 'CHILD':
            budgeted_expense += effective_budget
        elif not is_child_own_group:
            budgeted_expense += effective_budget

    for group in display_only_expense_groups_annotated:
        total_estimated = Decimal(str(group.total_estimated.amount)) if hasattr(group.total_estimated, 'amount') else (group.total_estimated or Decimal('0.00'))
        budgeted_amt = Decimal(str(group.budgeted_amount.amount)) if hasattr(group.budgeted_amount, 'amount') else Decimal(str(group.budgeted_amount))
        effective_budget = total_estimated if total_estimated > budgeted_amt else budgeted_amt

        if member_role_for_period != 'CHILD':
            budgeted_expense += effective_budget

    # Initialize return values
    recent_income_transactions = []
    income_flow_group_id = None
    kids_income_entries = []
    children_manual_income = {}
    budgeted_income = Decimal('0.00')
    realized_income = Decimal('0.00')
    realized_expense = Decimal('0.00')

    # Calculate income and realized expenses
    if member_role_for_period == 'CHILD':
        kids_groups = FlowGroup.objects.filter(
            family=family, period_start_date=start_date,
            is_kids_group=True, assigned_children=current_member
        )
        for kids_group in kids_groups:
            budg_amt = Decimal(str(kids_group.budgeted_amount.amount)) if hasattr(kids_group.budgeted_amount, 'amount') else Decimal(str(kids_group.budgeted_amount))
            kids_income_entries.append({
                'id': f'kids_{kids_group.id}', 'description': kids_group.name,
                'amount': budg_amt.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'date': start_date, 'realized': kids_group.realized, 'is_kids_income': True,
                'kids_group_id': kids_group.id, 'member': current_member,
            })
            budgeted_income += budg_amt
            if kids_group.realized:
                realized_income += budg_amt

        income_group = get_default_income_flow_group(family, current_member.user, start_date)
        manual_income_transactions = Transaction.objects.filter(
            flow_group=income_group, date__range=(start_date, end_date),
            member=current_member, is_child_manual_income=True
        ).select_related('member__user').order_by('-date', 'order')

        for trans in manual_income_transactions:
            amt = Decimal(str(trans.amount.amount)) if hasattr(trans.amount, 'amount') else Decimal(str(trans.amount))
            budgeted_income += amt
            if trans.realized:
                realized_income += amt
        
        recent_income_transactions = list(manual_income_transactions)
        income_flow_group_id = income_group.id

        realized_exp_q = Transaction.objects.filter(
            flow_group__in=accessible_expense_groups, date__range=(start_date, end_date),
            realized=True, is_child_expense=True
        ).filter(
            Q(flow_group__is_credit_card=False) | Q(flow_group__is_credit_card=True, flow_group__closed=True)
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        realized_expense = Decimal(str(realized_exp_q.amount)) if hasattr(realized_exp_q, 'amount') else realized_exp_q

    else: # PARENT/ADMIN
        income_group = get_default_income_flow_group(family, current_member.user, start_date)
        recent_income_transactions = Transaction.objects.filter(
            flow_group=income_group, date__range=(start_date, end_date), is_child_manual_income=False
        ).select_related('member__user').order_by('-date', 'order')
        income_flow_group_id = income_group.id

        budg_inc_q = Transaction.objects.filter(
            flow_group=income_group, date__range=(start_date, end_date), is_child_manual_income=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        budgeted_income = Decimal(str(budg_inc_q.amount)) if hasattr(budg_inc_q, 'amount') else budg_inc_q

        real_inc_q = Transaction.objects.filter(
            flow_group=income_group, date__range=(start_date, end_date),
            realized=True, is_child_manual_income=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        realized_income = Decimal(str(real_inc_q.amount)) if hasattr(real_inc_q, 'amount') else real_inc_q

        kids_realized_sum = FlowGroup.objects.filter(
            family=family, period_start_date=start_date, is_kids_group=True, realized=True
        ).aggregate(total=Sum('budgeted_amount'))['total'] or Decimal('0.00')
        kids_groups_realized_budget = Decimal(str(kids_realized_sum.amount)) if hasattr(kids_realized_sum, 'amount') else kids_realized_sum

        for child in family_members.filter(role='CHILD'):
            child_income = Transaction.objects.filter(
                flow_group=income_group, date__range=(start_date, end_date),
                member=child, is_child_manual_income=True
            )
            if child_income.exists():
                tot_q = child_income.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                real_tot_q = child_income.filter(realized=True).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                tot = Decimal(str(tot_q.amount)) if hasattr(tot_q, 'amount') else tot_q
                real_tot = Decimal(str(real_tot_q.amount)) if hasattr(real_tot_q, 'amount') else real_tot_q
                children_manual_income[child.id] = {
                    'member': child, 'total': tot, 'realized_total': real_tot,
                    'transactions': list(child_income.values('description', 'amount', 'date', 'realized'))
                }

        realized_exp_calc = Transaction.objects.filter(
            flow_group__in=accessible_expense_groups, date__range=(start_date, end_date),
            realized=True, is_child_expense=False
        ).filter(
            Q(flow_group__is_credit_card=False) | Q(flow_group__is_credit_card=True, flow_group__closed=True)
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        realized_expense = Decimal(str(realized_exp_calc.amount)) if hasattr(realized_exp_calc, 'amount') else realized_exp_calc
        realized_expense += kids_groups_realized_budget
    
    summary_totals = {
        'total_budgeted_income': budgeted_income.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
        'total_realized_income': realized_income.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
        'total_budgeted_expense': budgeted_expense.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
        'total_realized_expense': realized_expense.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
        'estimated_result': (budgeted_income - budgeted_expense).quantize(Decimal('0.01'), rounding=ROUND_DOWN),
        'realized_result': (realized_income - realized_expense).quantize(Decimal('0.01'), rounding=ROUND_DOWN),
    }

    return {
        'summary_totals': summary_totals,
        'recent_income_transactions': recent_income_transactions,
        'income_flow_group_id': income_flow_group_id,
        'kids_income_entries': kids_income_entries,
        'children_manual_income': children_manual_income,
        'budgeted_expense': budgeted_expense,
        'realized_expense': realized_expense,
    }