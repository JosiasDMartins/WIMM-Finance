import json
from decimal import Decimal, ROUND_DOWN
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.db import transaction as db_transaction
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.views.decorators.http import require_POST
from moneyed import Money

# Relative imports from the app (.. moves up one level, from /views/ to /finances/)
from ..models import (
    FamilyMember, FlowGroup, Transaction, Investment, BankBalance,
    FLOW_TYPE_INCOME, FLOW_TYPE_EXPENSE, EXPENSE_MAIN, EXPENSE_SECONDARY
)
from ..utils import (
    get_current_period_dates, 
    get_available_periods,
    check_period_change_impact, 
    close_current_period,
    ensure_period_exists,
    get_period_currency,
    get_member_role_for_period
)
from ..forms import (
    FamilyConfigurationForm, FlowGroupForm, InvestmentForm, 
    NewUserAndMemberForm
)

# Importing local utilities (same package /views/)
from .views_utils import (
    get_family_context,
    get_default_income_flow_group,
    get_visible_flow_groups_for_dashboard,
    can_access_flow_group,
    get_base_template_context,
    get_default_date_for_period,
    get_periods_history,
    get_year_to_date_metrics,
    get_currency_symbol,
    VERSION,
)


@login_required
def dashboard_view(request):
    family, current_member, family_members = get_family_context(request.user)
    if not family:
        # If there's no family, it could be a newly logged-in user after a restore
        # or an error. Redirecting to setup can be dangerous if a family already exists
        # Login should fail, but if it gets here...
        # Improvement: perhaps redirect to an "error" or "join" page
        return render(request, 'finances/setup.html') 

    query_period = request.GET.get('period')
    start_date, end_date, current_period_label = get_current_period_dates(family, query_period)
    
    config = getattr(family, 'configuration', None)
    if config:
        ensure_period_exists(family, start_date, end_date, config.period_type)
    
    member_role_for_period = get_member_role_for_period(current_member, start_date)
    
    accessible_expense_groups, display_only_expense_groups = get_visible_flow_groups_for_dashboard(
        family, 
        current_member, 
        start_date, 
        group_type_filter=FLOW_TYPE_EXPENSE
    )
    
    # Annotate accessible groups
    accessible_expense_groups = accessible_expense_groups.annotate(
        total_estimated=Sum(
            'transactions__amount',
            filter=Q(transactions__date__range=(start_date, end_date))
        ),
        total_spent=Sum(
            'transactions__amount',
            filter=Q(transactions__date__range=(start_date, end_date), transactions__realized=True)
        )
    ).order_by('order', 'name')
    
    # Annotate display-only groups
    display_only_expense_groups = display_only_expense_groups.annotate(
        total_estimated=Sum(
            'transactions__amount',
            filter=Q(transactions__date__range=(start_date, end_date))
        ),
        total_spent=Sum(
            'transactions__amount',
            filter=Q(transactions__date__range=(start_date, end_date), transactions__realized=True)
        )
    ).order_by('order', 'name')
    
    budgeted_expense = Decimal(0.00)
    
    # Process accessible groups
    for group in accessible_expense_groups:
        group.total_estimated = Decimal(str(group.total_estimated.amount)) if hasattr(group.total_estimated, 'amount') else (group.total_estimated or Decimal('0.00'))
        group.total_spent = Decimal(str(group.total_spent.amount)) if hasattr(group.total_spent, 'amount') else (group.total_spent or Decimal('0.00'))
        
        group.total_estimated = group.total_estimated.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        group.total_spent = group.total_spent.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        group.is_accessible = True
        
        if group.is_kids_group and member_role_for_period in ['ADMIN', 'PARENT']:
            child_exp = Transaction.objects.filter(
                flow_group=group,
                date__range=(start_date, end_date)
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            group.child_expenses = Decimal(str(child_exp.amount)) if hasattr(child_exp, 'amount') else child_exp
            
            group.is_child_group = False
            if group.owner:
                owner_member = FamilyMember.objects.filter(user=group.owner, family=family).first()
                if owner_member and owner_member.role == 'CHILD':
                    group.is_child_group = True
        
        budgeted_amt = Decimal(str(group.budgeted_amount.amount)) if hasattr(group.budgeted_amount, 'amount') else Decimal(str(group.budgeted_amount))
        
        group.budget_warning = group.total_estimated > budgeted_amt
        group.total_estimated = group.total_estimated if group.total_estimated > budgeted_amt else budgeted_amt
        
        is_child_own_group = False
        if group.owner:
            owner_member = FamilyMember.objects.filter(user=group.owner, family=family).first()
            if owner_member and owner_member.role == 'CHILD':
                is_child_own_group = True
        
        if not is_child_own_group:
            budgeted_expense = group.total_estimated + budgeted_expense
    
    # Process display-only groups
    for group in display_only_expense_groups:
        group.total_estimated = Decimal(str(group.total_estimated.amount)) if hasattr(group.total_estimated, 'amount') else (group.total_estimated or Decimal('0.00'))
        group.total_spent = Decimal(str(group.total_spent.amount)) if hasattr(group.total_spent, 'amount') else (group.total_spent or Decimal('0.00'))
        
        group.total_estimated = group.total_estimated.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        group.total_spent = group.total_spent.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        group.is_accessible = False
        
        budgeted_amt = Decimal(str(group.budgeted_amount.amount)) if hasattr(group.budgeted_amount, 'amount') else Decimal(str(group.budgeted_amount))
        
        group.budget_warning = group.total_estimated > budgeted_amt
        group.total_estimated = group.total_estimated if group.total_estimated > budgeted_amt else budgeted_amt
        
        budgeted_expense = group.total_estimated + budgeted_expense
    
    expense_groups = list(accessible_expense_groups) + list(display_only_expense_groups)

    # Income calculation
    if member_role_for_period == 'CHILD':
        # === CHILDREN VIEW ===
        kids_groups = FlowGroup.objects.filter(
            family=family,
            period_start_date=start_date,
            is_kids_group=True,
            assigned_children=current_member
        )
        
        kids_income_entries = []
        budgeted_income = Decimal('0.00')
        realized_income = Decimal('0.00')
        
        for kids_group in kids_groups:
            budg_amt = Decimal(str(kids_group.budgeted_amount.amount)) if hasattr(kids_group.budgeted_amount, 'amount') else Decimal(str(kids_group.budgeted_amount))
            
            kids_income_entries.append({
                'id': f'kids_{kids_group.id}',
                'description': kids_group.name,
                'amount': budg_amt.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'date': start_date,
                'realized': kids_group.realized,
                'is_kids_income': True,
                'kids_group_id': kids_group.id,
                'member': current_member,
            })
            budgeted_income += budg_amt
            if kids_group.realized:
                realized_income += budg_amt
        
        income_group = get_default_income_flow_group(family, request.user, start_date)
        manual_income_transactions = Transaction.objects.filter(
            flow_group=income_group,
            date__range=(start_date, end_date),
            member=current_member,
            is_child_manual_income=True
        ).select_related('member__user').order_by('-date', 'order')
        
        for trans in manual_income_transactions:
            amt = Decimal(str(trans.amount.amount)) if hasattr(trans.amount, 'amount') else Decimal(str(trans.amount))
            budgeted_income += amt
            if trans.realized:
                realized_income += amt
        
        recent_income_transactions = list(manual_income_transactions)
        income_flow_group_id = income_group.id
        context_kids_income = kids_income_entries

        realized_exp = Transaction.objects.filter(
            flow_group__in=accessible_expense_groups,
            date__range=(start_date, end_date),
            realized=True,
            is_child_expense=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        realized_expense = Decimal(str(realized_exp.amount)) if hasattr(realized_exp, 'amount') else realized_exp
        
    else:
        # === PARENTS/ADMINS VIEW ===
        income_group = get_default_income_flow_group(family, request.user, start_date)
        
        recent_income_transactions = Transaction.objects.filter(
            flow_group=income_group,
            date__range=(start_date, end_date),
            is_child_manual_income=False
        ).select_related('member__user').order_by('-date', 'order')
        
        income_flow_group_id = income_group.id
        
        budg_inc = Transaction.objects.filter(
            flow_group=income_group,
            date__range=(start_date, end_date),
            is_child_manual_income=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        budgeted_income = Decimal(str(budg_inc.amount)) if hasattr(budg_inc, 'amount') else budg_inc
        
        real_inc = Transaction.objects.filter(
            flow_group=income_group,
            date__range=(start_date, end_date),
            realized=True,
            is_child_manual_income=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        realized_income = Decimal(str(real_inc.amount)) if hasattr(real_inc, 'amount') else real_inc
        
        kids_realized_sum = FlowGroup.objects.filter(
            family=family,
            period_start_date=start_date,
            is_kids_group=True,
            realized=True
        ).aggregate(total=Sum('budgeted_amount'))['total'] or Decimal('0.00')
        
        kids_groups_realized_budget = Decimal(str(kids_realized_sum.amount)) if hasattr(kids_realized_sum, 'amount') else kids_realized_sum
            
        children_manual_income = {}
        for child in family_members:
            if child.role == 'CHILD':
                child_income = Transaction.objects.filter(
                    flow_group=income_group,
                    date__range=(start_date, end_date),
                    member=child,
                    is_child_manual_income=True
                )
                
                if child_income.exists():
                    tot = child_income.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                    real_tot = child_income.filter(realized=True).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                    
                    tot = Decimal(str(tot.amount)) if hasattr(tot, 'amount') else tot
                    real_tot = Decimal(str(real_tot.amount)) if hasattr(real_tot, 'amount') else real_tot
                    
                    children_manual_income[child.id] = {
                        'member': child,
                        'total': tot,
                        'realized_total': real_tot,
                        'transactions': list(child_income.values('description', 'amount', 'date', 'realized'))
                    }
        
        context_kids_income = []
        
        realized_exp_calc = Transaction.objects.filter(
            flow_group__in=accessible_expense_groups,
            date__range=(start_date, end_date),
            realized=True,
            is_child_expense=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        realized_expense = Decimal(str(realized_exp_calc.amount)) if hasattr(realized_exp_calc, 'amount') else realized_exp_calc
        realized_expense += kids_groups_realized_budget

    
    summary_totals = {
        'total_budgeted_income': (budgeted_income).quantize(Decimal('0.01'), rounding=ROUND_DOWN),
        'total_realized_income': (realized_income).quantize(Decimal('0.01'), rounding=ROUND_DOWN),
        'total_budgeted_expense': (budgeted_expense).quantize(Decimal('0.01'), rounding=ROUND_DOWN),
        'total_realized_expense': (realized_expense).quantize(Decimal('0.01'), rounding=ROUND_DOWN),
        'estimated_result': (budgeted_income - budgeted_expense).quantize(Decimal('0.01'), rounding=ROUND_DOWN),
        'realized_result': (realized_income - realized_expense).quantize(Decimal('0.01'), rounding=ROUND_DOWN),
    }

    default_date = get_default_date_for_period(start_date, end_date)
    
    child_can_create_groups = False
    if member_role_for_period == 'CHILD':
        child_manual_sum = Transaction.objects.filter(
            flow_group__group_type=FLOW_TYPE_INCOME,
            date__range=(start_date, end_date),
            member=current_member,
            is_child_manual_income=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        child_manual_income_total = Decimal(str(child_manual_sum.amount)) if hasattr(child_manual_sum, 'amount') else child_manual_sum
        child_can_create_groups = child_manual_income_total > Decimal('0.00')

    periods_history = get_periods_history(family, start_date)
    ytd_metrics = get_year_to_date_metrics(family, end_date)

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'current_period_label': current_period_label,
        'expense_groups': expense_groups,
        'recent_income_transactions': recent_income_transactions,
        'income_flow_group_id': income_flow_group_id,
        'family_members': family_members,
        'current_member': current_member,
        'member_role_for_period': member_role_for_period,
        'today_date': default_date.strftime('%Y-%m-%d'),
        'summary_totals': summary_totals,
        'child_can_create_groups': child_can_create_groups,
        'kids_income_entries': context_kids_income if member_role_for_period == 'CHILD' else [],
        'children_manual_income': children_manual_income if member_role_for_period in ['ADMIN', 'PARENT'] else {},
        'periods_history_json': json.dumps(periods_history),
        'ytd_metrics': ytd_metrics,
    }
        
    period_currency = get_period_currency(family, start_date)
    context['currency_symbol'] = get_currency_symbol(period_currency)
    context.update(get_base_template_context(family, query_period, start_date))
    
    return render(request, 'finances/dashboard.html', context)


@login_required
def configuration_view(request):
    """View for family settings."""
    family, current_member, family_members = get_family_context(request.user)
    
    try:
        member = FamilyMember.objects.select_related('family', 'family__configuration').get(user=request.user)
    except FamilyMember.DoesNotExist:
        messages.error(request, "You are not associated with any family.")
        return redirect('dashboard')
    
    if member.role not in ['ADMIN', 'PARENT']:
        messages.error(request, "Only Admins and Parents can access configuration.")
        return redirect('dashboard')
    
    family = member.family
    config = family.configuration

    old_config = {
        'period_type': config.period_type,
        'starting_day': config.starting_day,
        'base_date': config.base_date,
        'base_currency': config.base_currency
    }
    
    selected_period = request.GET.get('period')
    start_date, end_date, period_label = get_current_period_dates(family, selected_period)
    available_periods = get_available_periods(family)
    current_period_label = period_label
    
    config_obj = getattr(family, 'configuration', None)
    if config_obj:
        ensure_period_exists(family, start_date, end_date, config_obj.period_type)
    
    current_start, _, _ = get_current_period_dates(family, None)
    is_current_period = (start_date == current_start)
    
    if request.method == 'POST':
        form = FamilyConfigurationForm(request.POST, instance=config)
        if form.is_valid():
            new_config = form.cleaned_data

            config_changed = (
                old_config['period_type'] != new_config['period_type'] or
                old_config['starting_day'] != new_config['starting_day'] or
                old_config['base_date'] != new_config['base_date']
            )
            currency_changed = old_config['base_currency'] != new_config['base_currency']

            if config_changed:
                has_data, data_count = check_period_change_impact(family, start_date, end_date)
                if has_data:
                    messages.warning(
                        request,
                        f"Period configuration updated. Your current period has {data_count} items. "
                        f"This period will be preserved as-is, and the new configuration will apply to future periods."
                    )
                    close_current_period(family)
                else:
                    messages.info(request, "Period configuration updated. Changes will apply to the current and future periods.")

            if currency_changed:
                new_currency = new_config['base_currency']
                period = ensure_period_exists(family, start_date, end_date, config.period_type)
                
                if is_current_period:
                    # Período atual: Atualiza Config e Período
                    config.base_currency = new_currency
                    period.currency = new_currency
                    period.save()
                    
                    # Atualiza dados no período atual
                    updated_groups = FlowGroup.objects.filter(family=family, period_start_date=start_date).update(budgeted_amount_currency=new_currency)
                    updated_transactions = Transaction.objects.filter(flow_group__family=family, flow_group__period_start_date=start_date).update(amount_currency=new_currency)
                    updated_balances = BankBalance.objects.filter(family=family, period_start_date=start_date).update(amount_currency=new_currency)
                    updated_investments = Investment.objects.filter(family=family).update(amount_currency=new_currency) # Investimentos não são por período
                    
                    messages.success(
                        request,
                        f"Currency updated to {new_currency} for current period. "
                        f"Updated {updated_groups} groups, {updated_transactions} transactions, "
                        f"{updated_balances} bank balances, and {updated_investments} investments."
                    )
                else:
                    # Período passado: Atualiza APENAS Período
                    period.currency = new_currency
                    period.save()
                    
                    # Atualiza dados para este período específico
                    updated_groups = FlowGroup.objects.filter(family=family, period_start_date=start_date).update(budgeted_amount_currency=new_currency)
                    updated_transactions = Transaction.objects.filter(flow_group__family=family, flow_group__period_start_date=start_date).update(amount_currency=new_currency)
                    updated_balances = BankBalance.objects.filter(family=family, period_start_date=start_date).update(amount_currency=new_currency)

                    messages.success(
                        request,
                        f"Currency updated to {new_currency} for selected period only. "
                        f"Updated {updated_groups} groups, {updated_transactions} transactions, "
                        f"and {updated_balances} bank balances."
                    )
            
            # Nota: O código original tinha uma lógica complexa de atualização de Money
            # A lógica acima (atualizando _currency) é como o django-money *deveria* funcionar
            # Se não funcionar, a lógica de loop (como no original) será necessária.
            # Mantendo o save() principal
            form.save()
            
            messages.success(request, "Configuration updated successfully!")
            return redirect(f'/settings/?period={start_date.strftime("%Y-%m-%d")}')
    else:
        if not is_current_period:
            period_currency = get_period_currency(family, start_date)
            form = FamilyConfigurationForm(instance=config, initial={'base_currency': period_currency})
        else:
            form = FamilyConfigurationForm(instance=config)

    # Add members data for the Members tab
    context = {
        'form': form,
        'family': family,
        'family_members': family_members,
        'add_member_form': NewUserAndMemberForm(),
        'is_admin': current_member.role == 'ADMIN',
        'selected_period': selected_period,
        'start_date': start_date,
        'end_date': end_date,
        'period_label': period_label,
        'available_periods': available_periods,
        'current_period_label': current_period_label,
        'is_current_period': is_current_period,
        'VERSION': VERSION,
        'app_version': VERSION,
    }

    return render(request, 'finances/configurations.html', context)


@login_required
def bank_reconciliation_view(request):
    """View of bank reconciliation."""
    family, current_member, family_members = get_family_context(request.user)
    if not family:
        return redirect('dashboard')

    # Get tolerance configuration
    config = family.configuration
    tolerance = config.bank_reconciliation_tolerance

    query_period = request.GET.get('period')
    start_date, end_date, _ = get_current_period_dates(family, query_period)

    member_role_for_period = get_member_role_for_period(current_member, start_date)
    mode = request.GET.get('mode', 'general')
    
    bank_balances = BankBalance.objects.filter(
        family=family,
        period_start_date=start_date
    ).order_by('member', '-date')
    
    income_transactions = Transaction.objects.filter(
        flow_group__family=family,
        flow_group__period_start_date=start_date,
        flow_group__group_type=FLOW_TYPE_INCOME,
        date__range=(start_date, end_date),
        realized=True
    )
    
    expense_transactions = Transaction.objects.filter(
        flow_group__family=family,
        flow_group__period_start_date=start_date,
        flow_group__group_type__in=[EXPENSE_MAIN, EXPENSE_SECONDARY],
        date__range=(start_date, end_date),
        realized=True
    ).exclude(flow_group__is_investment=True)
    
    if mode == 'general':
        tot_inc = income_transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        tot_exp = expense_transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        total_income = Decimal(str(tot_inc.amount)) if hasattr(tot_inc, 'amount') else tot_inc
        total_expenses = Decimal(str(tot_exp.amount)) if hasattr(tot_exp, 'amount') else tot_exp
        
        calculated_balance = total_income - total_expenses
        
        tot_bank = bank_balances.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_bank_balance = Decimal(str(tot_bank.amount)) if hasattr(tot_bank, 'amount') else tot_bank
        
        discrepancy = total_bank_balance - calculated_balance
        discrepancy_percentage = abs(discrepancy / calculated_balance * 100) if calculated_balance != 0 else 0
        has_warning = discrepancy_percentage > tolerance
        
        reconciliation_data = {
            'mode': 'general',
            'total_income': total_income,
            'total_expenses': total_expenses.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
            'calculated_balance': calculated_balance.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
            'total_bank_balance': total_bank_balance.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
            'discrepancy': discrepancy.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
            'discrepancy_percentage': discrepancy_percentage.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
            'has_warning': has_warning,
        }
    else:
        # Modo 'detailed'
        members_data = []
        for member in family_members:
            mem_inc = income_transactions.filter(member=member).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            mem_exp = expense_transactions.filter(member=member).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            member_income = Decimal(str(mem_inc.amount)) if hasattr(mem_inc, 'amount') else mem_inc
            member_expenses = Decimal(str(mem_exp.amount)) if hasattr(mem_exp, 'amount') else mem_exp
            
            member_calculated_balance = member_income - member_expenses
            
            mem_bank = bank_balances.filter(member=member).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            member_bank_balance = Decimal(str(mem_bank.amount)) if hasattr(mem_bank, 'amount') else mem_bank
            
            member_discrepancy = member_bank_balance - member_calculated_balance
            member_discrepancy_percentage = abs(member_discrepancy / member_calculated_balance * 100) if member_calculated_balance != 0 else 0
            member_has_warning = member_discrepancy_percentage > tolerance
            
            members_data.append({
                'member': member,
                'income': member_income.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'expenses': member_expenses.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'calculated_balance': member_calculated_balance.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'bank_balance': member_bank_balance.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'discrepancy': member_discrepancy.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'discrepancy_percentage': member_discrepancy_percentage.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'has_warning': member_has_warning,
            })
        
        reconciliation_data = {
            'mode': 'detailed',
            'members_data': members_data,
        }
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'bank_balances': bank_balances,
        'family_members': family_members,
        'member_role_for_period': member_role_for_period,
        'reconciliation_data': reconciliation_data,
        'mode': mode,
    }
    context.update(get_base_template_context(family, query_period, start_date))
    
    return render(request, 'finances/bank_reconciliation.html', context)


@login_required
def create_flow_group_view(request):
    """View to create a new FlowGroup."""
    family, current_member, family_members = get_family_context(request.user)
    if not family:
        return redirect('dashboard')

    query_period = request.GET.get('period') or request.POST.get('period')
    start_date, end_date, _ = get_current_period_dates(family, query_period)

    if request.method == 'POST':
        form = FlowGroupForm(request.POST, family=family)
        if form.is_valid():
            flow_group = form.save(commit=False)
            flow_group.family = family
            flow_group.owner = request.user
            flow_group.group_type = EXPENSE_MAIN
            flow_group.period_start_date = start_date
            
            currency = get_period_currency(family, start_date)
            budget_decimal = form.cleaned_data.get('budgeted_amount')
            flow_group.budgeted_amount = Money(budget_decimal, currency)
            
            if current_member.role == 'CHILD':
                child_manual_sum = Transaction.objects.filter(
                    flow_group__group_type=FLOW_TYPE_INCOME,
                    flow_group__family=family,
                    date__range=(start_date, end_date),
                    member=current_member,
                    is_child_manual_income=True
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                
                child_manual_income_total = Decimal(str(child_manual_sum.amount)) if hasattr(child_manual_sum, 'amount') else child_manual_sum
                budget_value = flow_group.budgeted_amount.amount
                
                if budget_value > child_manual_income_total:
                    messages.error(request, f"Budget cannot exceed your available balance (${child_manual_income_total}).")
                    context = {
                        'form': form, 'start_date': start_date, 'end_date': end_date,
                        'current_member': current_member, 'child_max_budget': child_manual_income_total,
                    }
                    context.update(get_base_template_context(family, query_period, start_date))
                    return render(request, 'finances/add_flow_group.html', context)
                
                flow_group.is_shared = True
            
            if flow_group.is_kids_group:
                flow_group.is_shared = True
            
            flow_group.save()
            
            config = getattr(family, 'configuration', None)
            if config:
                ensure_period_exists(family, start_date, end_date, config.period_type)
            
            if current_member.role == 'CHILD':
                parents_admins = FamilyMember.objects.filter(family=family, role__in=['ADMIN', 'PARENT'])
                flow_group.assigned_members.set(parents_admins)
            else:
                form.save_m2m()
            
            messages.success(request, f"Flow Group '{flow_group.name}' created.")
            redirect_url = f"?period={start_date.strftime('%Y-%m-%d')}"
            return redirect(f"/flow-group/{flow_group.id}/edit/{redirect_url}")
    else:
        form = FlowGroupForm(family=family)

    default_date = get_default_date_for_period(start_date, end_date)
    
    child_max_budget = None
    if current_member.role == 'CHILD':
        child_sum = Transaction.objects.filter(
            flow_group__group_type=FLOW_TYPE_INCOME,
            flow_group__family=family,
            date__range=(start_date, end_date),
            member=current_member,
            is_child_manual_income=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.GET')
        
        child_max_budget = Decimal(str(child_sum.amount)) if hasattr(child_sum, 'amount') else child_sum

    context = {
        'form': form,
        'is_new': True,
        'family_members': family_members,
        'current_member': current_member,
        'today_date': default_date.strftime('%Y-%m-%d'),
        'start_date': start_date,
        'end_date': end_date,
        'child_max_budget': child_max_budget,
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/FlowGroup.html', context)


@login_required
def edit_flow_group_view(request, group_id):
    """View to edit an existing FlowGroup."""
    family, current_member, family_members = get_family_context(request.user)
    if not family:
        return redirect('dashboard')
        
    group = get_object_or_404(FlowGroup, id=group_id, family=family)
    
    if not can_access_flow_group(group, current_member):
        messages.error(request, "You don't have permission to access this group.")
        return redirect('dashboard')
    
    query_period = request.GET.get('period') or group.period_start_date.strftime('%Y-%m-%d')
    start_date, end_date, _ = get_current_period_dates(family, query_period)
    
    member_role_for_period = get_member_role_for_period(current_member, start_date)
    
    can_edit_group = (group.owner == request.user or current_member.role in ['ADMIN', 'PARENT'])
    can_edit_budget = can_edit_group
    if current_member.role == 'CHILD':
        can_edit_budget = False
    
    if request.method == 'POST' and can_edit_group:
        form = FlowGroupForm(request.POST, instance=group, family=family)
        if form.is_valid():
            flow_group = form.save(commit=False)
            
            currency = get_period_currency(family, start_date)
            budget_decimal = form.cleaned_data.get('budgeted_amount')
            flow_group.budgeted_amount = Money(budget_decimal, currency)
            
            if flow_group.is_kids_group:
                flow_group.is_shared = True
            
            flow_group.save()
            form.save_m2m()
            
            messages.success(request, f"Flow Group '{group.name}' updated.")
            redirect_url = f"?period={query_period}" if query_period else ""
            return redirect(f"/flow-group/{group_id}/edit/{redirect_url}")
    else:
        budget_initial = group.budgeted_amount.amount if hasattr(group.budgeted_amount, 'amount') else group.budgeted_amount
        form = FlowGroupForm(instance=group, family=family, initial={'budgeted_amount': budget_initial})

    transactions = Transaction.objects.filter(flow_group=group).select_related('member__user').order_by('order', '-date')
    
    total_est = transactions.filter(date__range=(start_date, end_date)).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    total_estimated = Decimal(str(total_est.amount)) if hasattr(total_est, 'amount') else total_est
    budg_amt_val = Decimal(str(group.budgeted_amount.amount)) if hasattr(group.budgeted_amount, 'amount') else Decimal(str(group.budgeted_amount))
    
    budget_warning = total_estimated > budg_amt_val if budg_amt_val else False

    default_date = get_default_date_for_period(start_date, end_date)
    period_currency = get_period_currency(family, start_date)
    currency_symbol = get_currency_symbol(period_currency)
    
    context = {
        'form': form,
        'is_new': False,
        'flow_group': group,
        'transactions': transactions,
        'family_members': family_members,
        'current_member': current_member,
        'today_date': default_date.strftime('%Y-%m-%d'),
        'total_estimated': total_estimated,
        'budget_warning': budget_warning,
        'start_date': start_date,
        'end_date': end_date,
        'can_edit_group': can_edit_group,
        'can_edit_budget': can_edit_budget,
        'member_role_for_period' : member_role_for_period,
        'currency_symbol': currency_symbol
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/FlowGroup.html', context)


@login_required
def members_view(request):
    """
    DEPRECATED: Members management is now integrated into the Settings page.
    This view redirects to Settings for backward compatibility.
    """
    query_period = request.GET.get('period')
    if query_period:
        return redirect(f'/settings/?period={query_period}')
    return redirect('configuration')


@login_required
@require_POST
@db_transaction.atomic
def add_member_view(request):
    """View (POST) to add a new member."""
    family, current_member, _ = get_family_context(request.user)
    if not family:
        messages.error(request, 'User is not associated with a family.')
        return redirect('members')
    
    if current_member.role != 'ADMIN':
        messages.error(request, 'Only admins can add new members.')
        return redirect('members')
    
    form = NewUserAndMemberForm(request.POST)
    query_period = request.GET.get('period')
    redirect_url = f"/members/?period={query_period}" if query_period else "/members/"
    
    if form.is_valid():
        try:
            UserModel = get_user_model()
            new_user = UserModel.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data.get('email', ''),
                password=form.cleaned_data['password']
            )
            
            FamilyMember.objects.create(
                user=new_user,
                family=family,
                role=form.cleaned_data['role']
            )
            messages.success(request, f"Member '{new_user.username}' added successfully!")
            
        except Exception as e:
            messages.error(request, f"Error creating member: {str(e)}")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
                
    return redirect(redirect_url)


@login_required
def edit_member_view(request, member_id):
    """View (POST-redirect) to edit a member."""
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return redirect('dashboard')
    
    if current_member.role != 'ADMIN':
        messages.error(request, 'Only admins can edit members.')
        return redirect('members')
    
    member = get_object_or_404(FamilyMember, id=member_id, family=family)
    query_period = request.GET.get('period')
    redirect_url = f"/members/?period={query_period}" if query_period else "/members/"
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_info':
            username = request.POST.get('username')
            email = request.POST.get('email', '')
            role = request.POST.get('role')
            
            if username:
                UserModel = get_user_model()
                if UserModel.objects.filter(username=username).exclude(id=member.user.id).exists():
                    messages.error(request, 'Username already taken.')
                else:
                    member.user.username = username
                    member.user.email = email
                    member.user.save()
                    member.role = role
                    member.save()
                    messages.success(request, 'Member information updated successfully.')
            
        elif action == 'change_password':
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            if new_password and new_password == confirm_password:
                member.user.set_password(new_password)
                member.user.save()
                messages.success(request, 'Password changed successfully.')
            else:
                messages.error(request, 'Passwords do not match.')
        
    return redirect(redirect_url)


@login_required
@require_POST
def remove_member_view(request, member_id):
    """View (POST) to remove a member."""
    family, current_member, _ = get_family_context(request.user)
    if not family:
        messages.error(request, 'User is not associated with a family.')
        return redirect('members')
    
    if current_member.role != 'ADMIN':
        messages.error(request, 'Only admins can remove members.')
        return redirect('members')
    
    member_to_remove = get_object_or_404(FamilyMember, id=member_id, family=family)
    
    if member_to_remove.user == request.user:
        messages.error(request, 'You cannot remove yourself from the family.')
        return redirect('members')
    
    username = member_to_remove.user.username
    member_to_remove.delete()
    
    messages.success(request, f'Member {username} has been removed from the family.')
    
    query_period = request.GET.get('period')
    redirect_url = f"/members/?period={query_period}" if query_period else "/members/"
    return redirect(redirect_url)


@login_required
def investments_view(request):
    """View for managing investments."""
    family, _, _ = get_family_context(request.user)
    if not family:
        return redirect('dashboard')
    
    query_period = request.GET.get('period')
    
    if request.method == 'POST':
        form = InvestmentForm(request.POST)
        if form.is_valid():
            investment = form.save(commit=False)
            investment.family = family
            investment.save()
            messages.success(request, 'Investment added.')
            redirect_url = f"/investments/?period={query_period}" if query_period else "/investments/"
            return redirect(redirect_url)
    else:
        form = InvestmentForm()

    investments = Investment.objects.filter(family=family).order_by('name')
    start_date, end_date, _ = get_current_period_dates(family, query_period)
    
    context = {
        'investment_form': form,
        'family_investments': investments,
        'start_date': start_date,
        'end_date': end_date,
        'currency_symbol': get_currency_symbol(family.configuration.base_currency),
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/invest.html', context)


@login_required
def add_receipt_view(request):
    """Shortcut to add a recipe (redirects to the income group)."""
    family, _, _ = get_family_context(request.user)
    query_period = request.GET.get('period')
    start_date, _, _ = get_current_period_dates(family, query_period)
    income_group = get_default_income_flow_group(family, request.user, start_date)
    
    redirect_url = f"?period={query_period}" if query_period else ""
    return redirect(f"/flow-group/{income_group.id}/edit/{redirect_url}")


@login_required
@require_POST 
def investment_add_view(request):
    """View (POST-redirect) para adicionar investimento (provavelmente um formulário no investments_view)."""
    query_period = request.GET.get('period')
    redirect_url = f"/investments/?period={query_period}" if query_period else "/investments/"
    # A lógica de salvar está no 'investments_view'
    return redirect(redirect_url)