import json
from decimal import Decimal, ROUND_DOWN
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.db import transaction as db_transaction
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.utils.translation import gettext as _
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
    get_decimal_separator,
    get_thousand_separator,
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

    # Ensure recurring FlowGroups and fixed transactions are created for this period
    from ..recurring_utils import ensure_recurring_data_for_period
    ensure_recurring_data_for_period(family, start_date)

    member_role_for_period = get_member_role_for_period(current_member, start_date)
    
    accessible_expense_groups, display_only_expense_groups = get_visible_flow_groups_for_dashboard(
        family, 
        current_member, 
        start_date, 
        group_type_filter=FLOW_TYPE_EXPENSE
    )
    
    # Annotate accessible groups
    # For credit card groups: only count realized if closed=True
    accessible_expense_groups = accessible_expense_groups.annotate(
        total_estimated=Sum(
            'transactions__amount',
            filter=Q(transactions__date__range=(start_date, end_date))
        ),
        total_spent=Sum(
            'transactions__amount',
            filter=Q(
                transactions__date__range=(start_date, end_date),
                transactions__realized=True
            ) & (
                Q(is_credit_card=False) | Q(is_credit_card=True, closed=True)
            )
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
            filter=Q(
                transactions__date__range=(start_date, end_date),
                transactions__realized=True
            ) & (
                Q(is_credit_card=False) | Q(is_credit_card=True, closed=True)
            )
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

        # For CHILD users: only count their own groups in budgeted_expense
        # For ADMIN/PARENT: count all non-child-owned groups
        if member_role_for_period == 'CHILD':
            # Child: only their own groups
            budgeted_expense = group.total_estimated + budgeted_expense
        elif not is_child_own_group:
            # Admin/Parent: all groups except child-owned ones
            budgeted_expense = group.total_estimated + budgeted_expense

    # Process display-only groups (only for ADMIN/PARENT, not for CHILD)
    for group in display_only_expense_groups:
        group.total_estimated = Decimal(str(group.total_estimated.amount)) if hasattr(group.total_estimated, 'amount') else (group.total_estimated or Decimal('0.00'))
        group.total_spent = Decimal(str(group.total_spent.amount)) if hasattr(group.total_spent, 'amount') else (group.total_spent or Decimal('0.00'))

        group.total_estimated = group.total_estimated.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        group.total_spent = group.total_spent.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        group.is_accessible = False

        budgeted_amt = Decimal(str(group.budgeted_amount.amount)) if hasattr(group.budgeted_amount, 'amount') else Decimal(str(group.budgeted_amount))

        group.budget_warning = group.total_estimated > budgeted_amt
        group.total_estimated = group.total_estimated if group.total_estimated > budgeted_amt else budgeted_amt

        # Only add display-only groups to expense for ADMIN/PARENT
        if member_role_for_period != 'CHILD':
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
    ytd_metrics = get_year_to_date_metrics(family, end_date, current_member)

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
    context['decimal_separator'] = get_decimal_separator()
    context['thousand_separator'] = get_thousand_separator()
    context.update(get_base_template_context(family, query_period, start_date))

    return render(request, 'finances/dashboard.html', context)


@login_required
def configuration_view(request):
    """View for family settings."""
    family, current_member, family_members = get_family_context(request.user)

    try:
        member = FamilyMember.objects.select_related('family', 'family__configuration').get(user=request.user)
    except FamilyMember.DoesNotExist:
        messages.error(request, _("You are not associated with any family."))
        return redirect('dashboard')

    # Block Child users from accessing settings
    if member.role == 'CHILD':
        messages.error(request, _("Child users cannot access system settings."))
        return redirect('dashboard')

    if member.role not in ['ADMIN', 'PARENT']:
        messages.error(request, _("Only Admins and Parents can access configuration."))
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
    
    current_start, _unused1, _unused2 = get_current_period_dates(family, None)
    is_current_period = (start_date == current_start)
    
    if request.method == 'POST':
        # Debug logging
        import logging
        from django.conf import settings
        logger = logging.getLogger(__name__)
        debug_enabled = getattr(settings, 'DEBUG', False)
        

        if debug_enabled:
            print(f"[DEBUG PERIOD] [configuration_view] POST request received")
            print(f"[DEBUG PERIOD]  User: {request.user.username}")
            print(f"[DEBUG PERIOD]  Member role: {member.role}")
            print(f"[DEBUG PERIOD]  Is AJAX: {request.headers.get('x-requested-with') == 'XMLHttpRequest'}")

        form = FamilyConfigurationForm(request.POST, instance=config)
        print(f"[DEBUG PERIOD] [configuration_view] Form is_valid: {form.is_valid()}")
        if not form.is_valid():
            print(f"[DEBUG PERIOD] [configuration_view] Form errors: {form.errors}")

        if form.is_valid():
            new_config = form.cleaned_data

            # Only admin can change period configuration
            if member.role != 'ADMIN':
                new_config['period_type'] = old_config['period_type']
                new_config['starting_day'] = old_config['starting_day']
                new_config['base_date'] = old_config['base_date']

            config_changed = (
                old_config['period_type'] != new_config['period_type'] or
                old_config['starting_day'] != new_config['starting_day'] or
                old_config['base_date'] != new_config['base_date']
            )
            currency_changed = old_config['base_currency'] != new_config['base_currency']

            # Flag to track if we manually saved the config (to avoid double save)
            config_manually_saved = False
            impact = None

            # Check if this is a confirmed period change (from modal)
            period_change_confirmed = request.POST.get('confirm_period_change') == 'true'

            print(f"[DEBUG PERIOD] [configuration_view] Form valid, checking changes:")
            print(f"[DEBUG PERIOD]   old_config period_type: {old_config['period_type']}")
            print(f"[DEBUG PERIOD]   new_config period_type: {new_config['period_type']}")
            print(f"[DEBUG PERIOD]   config_changed: {config_changed}")
            print(f"[DEBUG PERIOD]   period_change_confirmed: {period_change_confirmed}")

            if config_changed:
                print(f"[DEBUG PERIOD] [configuration_view] Config changed, calling check_period_change_impact")

                # Call check_period_change_impact with correct parameters
                # CRITICAL: Pass old values from old_config captured at view start
                # This prevents issues if database was modified in previous failed attempts
                impact = check_period_change_impact(
                    family,
                    new_config['period_type'],
                    new_starting_day=new_config['starting_day'],
                    new_base_date=new_config['base_date'],
                    old_period_type=old_config['period_type'],      # Use captured old values, not DB
                    old_starting_day=old_config['starting_day'],
                    old_base_date=old_config['base_date']
                )

                print(f"[DEBUG PERIOD] [configuration_view] Impact result: requires_close={impact['requires_close']}")

                if impact['requires_close']:
                    # STEP 1: If NOT confirmed yet, return modal data as JSON
                    if not period_change_confirmed:
                        # Prepare impact data for modal
                        from django.http import JsonResponse

                        # Calculate period days
                        current_period_days = (impact['current_period'][1] - impact['current_period'][0]).days + 1
                        new_period_days = (impact['new_current_period'][1] - impact['new_current_period'][0]).days + 1

                        # Period type labels
                        period_types_dict = dict(config.PERIOD_TYPES)
                        old_period_type_label = period_types_dict.get(old_config['period_type'], old_config['period_type'])
                        new_period_type_label = period_types_dict.get(new_config['period_type'], new_config['period_type'])

                        modal_data = {
                            'requires_confirmation': True,
                            'old_period_type_label': old_period_type_label,
                            'new_period_type_label': new_period_type_label,
                            'current_period_label': impact['current_period'][2],
                            'current_period_days': current_period_days,
                            'new_period_label': impact['new_current_period'][2],
                            'new_period_days': new_period_days,
                            'message': str(impact['message']),  # Force lazy translation to string
                        }

                        # Adjustment period data (if exists)
                        if impact['adjustment_period']:
                            adj_start, adj_end = impact['adjustment_period']
                            adj_days = (adj_end - adj_start).days + 1
                            adj_label = f"{adj_start.strftime('%b %d')} - {adj_end.strftime('%b %d, %Y')}"

                            modal_data['adjustment_period'] = True
                            modal_data['adjustment_period_label'] = adj_label
                            modal_data['adjustment_period_days'] = adj_days
                        else:
                            modal_data['adjustment_period'] = False

                        return JsonResponse(modal_data)

                    # STEP 2: If confirmed, apply the changes
                    else:
                        # IMPORTANT: Save ALL form fields first (including period config)
                        # We need the new period config in the database before apply_period_configuration_change
                        form.save()
                        config_manually_saved = True

                        # Reload config to ensure we have fresh data
                        config.refresh_from_db()

                        # Enrich old_config and new_config with period boundaries from impact
                        old_config['current_start'] = impact['current_period'][0]
                        old_config['current_end'] = impact['current_period'][1]

                        new_config['new_start'] = impact['new_current_period'][0]
                        new_config['new_end'] = impact['new_current_period'][1]

                        # Apply the period configuration change
                        from finances.utils import apply_period_configuration_change
                        results = apply_period_configuration_change(
                            family,
                            old_config,
                            new_config,
                            adjustment_period=impact['adjustment_period']
                        )
                        messages.success(
                            request,
                            _("Period configuration updated successfully. Created %(periods)s new periods and copied %(groups)s flow groups.") % {
                                'periods': len(results['periods_created']),
                                'groups': results['flow_groups_copied']
                            }
                        )
                else:
                    # No adjustment needed, just save
                    messages.info(request, _("Period configuration updated. Changes will apply to the current and future periods."))

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
                        _("Currency updated to %(currency)s for current period. Updated %(groups)s groups, %(transactions)s transactions, %(balances)s bank balances, and %(investments)s investments.") % {
                            'currency': new_currency,
                            'groups': updated_groups,
                            'transactions': updated_transactions,
                            'balances': updated_balances,
                            'investments': updated_investments
                        }
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
                        _("Currency updated to %(currency)s for selected period only. Updated %(groups)s groups, %(transactions)s transactions, and %(balances)s bank balances.") % {
                            'currency': new_currency,
                            'groups': updated_groups,
                            'transactions': updated_transactions,
                            'balances': updated_balances
                        }
                    )
            
            # Nota: O código original tinha uma lógica complexa de atualização de Money
            # A lógica acima (atualizando _currency) é como o django-money *deveria* funcionar
            # Se não funcionar, a lógica de loop (como no original) será necessária.

            # Only save if we haven't manually saved the period config already
            if not config_manually_saved:
                form.save()

            # Only show generic success message if we didn't already show a specific one
            if not (config_changed and impact.get('requires_close')):
                messages.success(request, _("Configuration updated successfully!"))

            return redirect(f'/settings/?period={start_date.strftime("%Y-%m-%d")}')
    else:
        if not is_current_period:
            period_currency = get_period_currency(family, start_date)
            form = FamilyConfigurationForm(instance=config, initial={'base_currency': period_currency})
        else:
            form = FamilyConfigurationForm(instance=config)

    # Disable period configuration fields for non-admin users
    if member.role != 'ADMIN':
        form.fields['period_type'].widget.attrs['disabled'] = 'disabled'
        form.fields['starting_day'].widget.attrs['disabled'] = 'disabled'
        form.fields['base_date'].widget.attrs['disabled'] = 'disabled'

    # Add members data for the Members tab
    # Add permission checks for each member
    from ..permissions import can_edit_user, can_change_password, can_delete_user

    # Create a list of members with their permission info
    members_with_permissions = []
    for member in family_members:
        members_with_permissions.append({
            'member': member,
            'can_edit': can_edit_user(current_member, member),
            'can_change_password': can_change_password(current_member, member),
            'can_delete': can_delete_user(current_member, member),
        })

    context = {
        'form': form,
        'family': family,
        'family_members': family_members,
        'members_with_permissions': members_with_permissions,
        'add_member_form': NewUserAndMemberForm(),
        'is_admin': current_member.role == 'ADMIN',
        'is_parent': current_member.role == 'PARENT',
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
    start_date, end_date, _unused = get_current_period_dates(family, query_period)

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
        'decimal_separator': get_decimal_separator(),
        'thousand_separator': get_thousand_separator(),
        'currency_symbol': get_currency_symbol(get_period_currency(family, start_date)),
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
    start_date, end_date, _unused = get_current_period_dates(family, query_period)

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
                    messages.error(request, _("Budget cannot exceed your available balance (%(balance)s).") % {'balance': f'${child_manual_income_total}'})
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

            messages.success(request, _("Flow Group '%(name)s' created.") % {'name': flow_group.name})
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
        'decimal_separator': get_decimal_separator(),
        'thousand_separator': get_thousand_separator(),
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
        messages.error(request, _("You don't have permission to access this group."))
        return redirect('dashboard')
    
    query_period = request.GET.get('period') or group.period_start_date.strftime('%Y-%m-%d')
    start_date, end_date, _unused = get_current_period_dates(family, query_period)

    # Ensure recurring FlowGroups and fixed transactions are created for this period
    from ..recurring_utils import ensure_recurring_data_for_period
    ensure_recurring_data_for_period(family, start_date)

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

            messages.success(request, _("Flow Group '%(name)s' updated.") % {'name': group.name})
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
        'currency_symbol': currency_symbol,
        'decimal_separator': get_decimal_separator(),
        'thousand_separator': get_thousand_separator(),
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
    from ..permissions import can_create_user
    from django.conf import settings

    # Block user creation in demo mode
    if getattr(settings, 'DEMO_MODE', False):
        messages.error(request, _('User creation is disabled in demo mode.'))
        query_period = request.GET.get('period')
        redirect_url = f"/settings/?period={query_period}" if query_period else "/settings/"
        return redirect(redirect_url)

    family, current_member, _unused = get_family_context(request.user)
    if not family:
        messages.error(request, _('User is not associated with a family.'))
        return redirect('configuration')

    query_period = request.GET.get('period')
    redirect_url = f"/settings/?period={query_period}" if query_period else "/settings/"

    form = NewUserAndMemberForm(request.POST)

    if form.is_valid():
        target_role = form.cleaned_data['role']

        # Check permission to create this type of user
        if not can_create_user(current_member, target_role):
            if current_member.role == 'PARENT':
                messages.error(request, _('Parents can only create CHILD users.'))
            else:
                messages.error(request, _('You do not have permission to create users.'))
            return redirect(redirect_url)

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
                role=target_role
            )
            messages.success(request, _("Member '%(username)s' added successfully!") % {'username': new_user.username})

        except Exception as e:
            messages.error(request, _("Error creating member: %(error)s") % {'error': str(e)})
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")

    return redirect(redirect_url)


@login_required
def edit_member_view(request, member_id):
    """View (POST-redirect) to edit a member."""
    from ..permissions import can_edit_user, can_change_password

    family, current_member, _unused = get_family_context(request.user)
    if not family:
        return redirect('dashboard')

    member = get_object_or_404(FamilyMember, id=member_id, family=family)
    query_period = request.GET.get('period')
    redirect_url = f"/settings/?period={query_period}" if query_period else "/settings/"

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_info':
            # Block user editing in demo mode
            from django.conf import settings
            if getattr(settings, 'DEMO_MODE', False):
                messages.error(request, _('User editing is disabled in demo mode.'))
                return redirect(redirect_url)

            # Check permission to edit user info
            if not can_edit_user(current_member, member):
                messages.error(request, _('You do not have permission to edit this user.'))
                return redirect(redirect_url)

            username = request.POST.get('username')
            email = request.POST.get('email', '')
            role = request.POST.get('role')

            if username:
                UserModel = get_user_model()
                if UserModel.objects.filter(username=username).exclude(id=member.user.id).exists():
                    messages.error(request, _('Username already taken.'))
                else:
                    member.user.username = username
                    member.user.email = email
                    member.user.save()

                    # Only allow role changes if user has permission
                    # Admin can change any role, Parent can change Child roles
                    if current_member.role == 'ADMIN':
                        member.role = role
                        member.save()
                        messages.success(request, _('Member information updated successfully.'))
                    elif current_member.role == 'PARENT' and member.role == 'CHILD':
                        # Parents cannot change role, only edit name/email
                        messages.success(request, _('Member information updated successfully.'))
                    elif current_member.id == member.id:
                        # User editing themselves cannot change role
                        messages.success(request, _('Profile updated successfully.'))
                    else:
                        messages.success(request, _('Member information updated successfully.'))

        elif action == 'change_password':
            # Block password changes in demo mode
            from django.conf import settings
            if getattr(settings, 'DEMO_MODE', False):
                messages.error(request, _('Password changes are disabled in demo mode.'))
                return redirect(redirect_url)

            # Check permission to change password
            if not can_change_password(current_member, member):
                messages.error(request, _("You do not have permission to change this user's password."))
                return redirect(redirect_url)

            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')

            if len(new_password) < 6:
                messages.error(request, _('Password must be at least 6 characters long.'))
            elif new_password and new_password == confirm_password:
                member.user.set_password(new_password)
                member.user.save()
                messages.success(request, _('Password changed successfully.'))
            else:
                messages.error(request, _('Passwords do not match.'))

    return redirect(redirect_url)


@login_required
@require_POST
def remove_member_view(request, member_id):
    """View (POST) to remove a member."""
    from ..permissions import can_delete_user
    from django.conf import settings

    # Block user deletion in demo mode
    if getattr(settings, 'DEMO_MODE', False):
        messages.error(request, _('User deletion is disabled in demo mode.'))
        query_period = request.GET.get('period')
        redirect_url = f"/settings/?period={query_period}" if query_period else "/settings/"
        return redirect(redirect_url)

    family, current_member, _unused = get_family_context(request.user)
    if not family:
        messages.error(request, _('User is not associated with a family.'))
        return redirect('configuration')

    member_to_remove = get_object_or_404(FamilyMember, id=member_id, family=family)

    # Check permission to delete this user
    if not can_delete_user(current_member, member_to_remove):
        if current_member.id == member_to_remove.id:
            messages.error(request, _('You cannot remove yourself from the family.'))
        elif current_member.role == 'PARENT':
            messages.error(request, _('Parents can only remove CHILD users.'))
        else:
            messages.error(request, _('You do not have permission to remove this user.'))

        query_period = request.GET.get('period')
        redirect_url = f"/settings/?period={query_period}" if query_period else "/settings/"
        return redirect(redirect_url)

    username = member_to_remove.user.username
    member_to_remove.delete()

    messages.success(request, _('Member %(username)s has been removed from the family.') % {'username': username})

    query_period = request.GET.get('period')
    redirect_url = f"/settings/?period={query_period}" if query_period else "/settings/"
    return redirect(redirect_url)


@login_required
def investments_view(request):
    """View for managing investments."""
    family, current_member, _unused2 = get_family_context(request.user)
    if not family:
        return redirect('dashboard')

    # Block Child users from accessing investments
    if current_member.role == 'CHILD':
        messages.error(request, _("Child users cannot access investments."))
        return redirect('dashboard')
    
    query_period = request.GET.get('period')
    
    if request.method == 'POST':
        form = InvestmentForm(request.POST)
        if form.is_valid():
            investment = form.save(commit=False)
            investment.family = family
            investment.save()
            messages.success(request, _('Investment added.'))
            redirect_url = f"/investments/?period={query_period}" if query_period else "/investments/"
            return redirect(redirect_url)
    else:
        form = InvestmentForm()

    investments = Investment.objects.filter(family=family).order_by('name')
    start_date, end_date, _unused = get_current_period_dates(family, query_period)

    # Calculate available investment balance from FlowGroups marked as investment
    # Sum all realized transactions in investment FlowGroups (YTD - Year to Date)
    from datetime import date
    year_start = date(end_date.year, 1, 1)

    investment_balance = Transaction.objects.filter(
        flow_group__family=family,
        flow_group__is_investment=True,
        date__range=(year_start, end_date),
        realized=True
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Convert Money to Decimal
    available_balance = Decimal(str(investment_balance.amount)) if hasattr(investment_balance, 'amount') else investment_balance

    context = {
        'investment_form': form,
        'family_investments': investments,
        'start_date': start_date,
        'end_date': end_date,
        'currency_symbol': get_currency_symbol(family.configuration.base_currency),
        'available_balance': available_balance.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/invest.html', context)


@login_required
def add_receipt_view(request):
    """Shortcut to add a recipe (redirects to the income group)."""
    family, _unused1, _unused2 = get_family_context(request.user)
    query_period = request.GET.get('period')
    start_date, _unused1, _unused2 = get_current_period_dates(family, query_period)
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


@login_required
@require_POST
def mark_admin_warning_seen(request):
    """
    Marks that the admin warning modal has been seen in this session.
    This prevents the modal from appearing again until the next login.
    """
    request.session['admin_warning_seen'] = True
    from django.http import JsonResponse
    return JsonResponse({'status': 'ok'})