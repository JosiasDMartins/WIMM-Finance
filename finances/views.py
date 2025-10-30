# finances/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Max
from django.db import transaction as db_transaction
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponse
from django.views.decorators.http import require_POST 
from django.contrib.auth import get_user_model 
from django.contrib import messages 
from django.db.models import Q 

from django.utils import timezone
import json
from datetime import datetime as dt_datetime 
from decimal import Decimal

# Import Models
from .models import (
    Family, FamilyMember, FlowGroup, Transaction, Investment, FamilyConfiguration,
    FLOW_TYPE_INCOME, EXPENSE_MAIN, EXPENSE_SECONDARY, FLOW_TYPE_EXPENSE 
)

# Import Forms
from .forms import (
    FamilyConfigurationForm, FlowGroupForm, InvestmentForm, 
    AddMemberForm, NewUserAndMemberForm
)

# Import Utility Functions
from .utils import get_current_period_dates, get_period_options_context as get_period_options

# === Utility Function to get Family Context ===
def get_family_context(user):
    """Retrieves the Family and FamilyMember context for the logged-in user."""
    try:
        family_member = FamilyMember.objects.select_related('family').get(user=user)
        family = family_member.family
        all_family_members = FamilyMember.objects.filter(family=family).select_related('user').order_by('user__username')
        return family, family_member, all_family_members
    except FamilyMember.DoesNotExist:
        return None, None, []

# === Utility Function for default Income Group ===
def get_default_income_flow_group(family, user):
    """Retrieves or creates the default income FlowGroup for the family."""
    income_group, created = FlowGroup.objects.get_or_create(
        family=family,
        group_type=FLOW_TYPE_INCOME,
        defaults={'name': 'Income (Default)', 'budgeted_amount': Decimal('0.00'), 'owner': user}
    )
    return income_group

# === Utility Wrapper for Period Context ===
def get_base_template_context(family, query_period, start_date):
    """
    Gets the context required by base.html (period selector).
    """
    # Fix for base.html: It expects 'is_current' boolean
    current_period_value = query_period if query_period else start_date.strftime("%Y-%m")
    period_options = []
    for period in get_period_options(family, start_date):
        period_options.append({
            'label': period['label'],
            'value': period['value'],
            'is_current': period['value'] == current_period_value
        })
    
    return {
        'period_options': period_options
    }

# === Core Views ===

@login_required
def dashboard_view(request):
    family, current_member, family_members = get_family_context(request.user)
    if not family:
        return render(request, 'finances/setup.html') 

    query_period = request.GET.get('period')
    start_date, end_date, current_period_label = get_current_period_dates(family, query_period)
    
    expense_group_q = Q(group_type=EXPENSE_MAIN) | Q(group_type=EXPENSE_SECONDARY)
    
    expense_groups = FlowGroup.objects.filter(
        expense_group_q,
        family=family,
    ).annotate(
        total_spent=Sum(
            'transactions__amount',
            filter=Q(transactions__date__range=(start_date, end_date))
        )
    ).order_by('order', 'name')
    
    for group in expense_groups:
        group.total_spent = group.total_spent if group.total_spent is not None else Decimal('0.00')

    income_group = get_default_income_flow_group(family, request.user)
    
    # FIX: Renamed to match the restored dashboard.html template
    recent_income_transactions = Transaction.objects.filter(
        flow_group=income_group,
        date__range=(start_date, end_date)
    ).select_related('member__user').order_by('-date', 'order') # Order by most recent
    
    expense_filter_budget = Q(group_type__in=FLOW_TYPE_EXPENSE)
    
    summary_totals = FlowGroup.objects.filter(family=family).aggregate(
        total_budgeted_income=Sum('transactions__amount', filter=Q(group_type=FLOW_TYPE_INCOME, transactions__date__range=(start_date, end_date))),  #Should be the same as realized, because there is no budget for income for
        total_budgeted_expense=Sum('budgeted_amount', filter=expense_filter_budget),
        total_realized_income=Sum('transactions__amount', filter=Q(group_type=FLOW_TYPE_INCOME, transactions__date__range=(start_date, end_date))),
        total_realized_expense=Sum('transactions__amount', filter=Q(group_type__in=FLOW_TYPE_EXPENSE, transactions__date__range=(start_date, end_date))),
    )
    
    budgeted_income = summary_totals.get('total_budgeted_income') or Decimal('0.00')
    budgeted_expense = summary_totals.get('total_budgeted_expense') or Decimal('0.00')
    realized_income = summary_totals.get('total_realized_income') or Decimal('0.00')
    realized_expense = summary_totals.get('total_realized_expense') or Decimal('0.00')
    
    summary_totals['estimated_result'] = budgeted_income - budgeted_expense
    summary_totals['realized_result'] = realized_income - realized_expense

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'current_period_label': current_period_label,
        'expense_groups': expense_groups,
        'recent_income_transactions': recent_income_transactions, # FIX: Renamed variable
        'family_members': family_members,
        'summary_totals': summary_totals,
    }
    
    # Add base.html context
    context.update(get_base_template_context(family, query_period, start_date))
    
    return render(request, 'finances/dashboard.html', context)


# === AJAX Endpoints ===

@login_required
@require_POST
@db_transaction.atomic
def save_flow_item_ajax(request):
    """
    Handles AJAX request to save or update a Transaction.
    This view matches the JS in FlowGroup.html.
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")
    
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")

    try:
        data = json.loads(request.body)
        
        flow_group_id = data.get('flow_group_id')
        transaction_id = data.get('transaction_id') 
        description = data.get('description')
        amount_str = data.get('amount')
        date_str = data.get('date')
        member_id = data.get('member_id') # From FlowGroup.html JS
        
        if not all([flow_group_id, description, amount_str, date_str, member_id]):
            return JsonResponse({'error': 'Missing required fields.'}, status=400)
            
        amount = Decimal(amount_str)
        date = dt_datetime.strptime(date_str, '%Y-%m-%d').date()

        flow_group = get_object_or_404(FlowGroup, id=flow_group_id, family=family)
        member = get_object_or_404(FamilyMember, id=member_id, family=family)

        if transaction_id and transaction_id != '0':
            transaction = get_object_or_404(Transaction, id=transaction_id, flow_group=flow_group)
        else:
            max_order = Transaction.objects.filter(flow_group=flow_group).aggregate(max_order=Max('order'))['max_order']
            new_order = (max_order or 0) + 1
            transaction = Transaction(
                flow_group=flow_group,
                order=new_order
            )

        transaction.description = description
        transaction.amount = abs(amount) 
        transaction.date = date
        transaction.member = member # Assign member from form
        transaction.save()

        return JsonResponse({
            'status': 'success',
            'transaction_id': transaction.id,
            'description': transaction.description,
            'amount': str(transaction.amount),
            'date': transaction.date.strftime('%Y-%m-%d'), # JS expects YYYY-MM-DD
            'member_id': transaction.member.id,
            'member_name': transaction.member.user.username,
        })

    except Exception as e:
        return JsonResponse({'error': f'A server error occurred: {str(e)}'}, status=500)


@login_required
@require_POST
@db_transaction.atomic
def delete_flow_item_ajax(request):
    """Handles AJAX request to delete a single Transaction item."""
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")

    family, _, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")

    try:
        data = json.loads(request.body)
        transaction_id = data.get('transaction_id')

        if not transaction_id:
            return JsonResponse({'error': 'Missing transaction_id.'}, status=400)

        transaction = get_object_or_404(Transaction, id=transaction_id, flow_group__family=family)
        
        transaction.delete()

        return JsonResponse({'status': 'success', 'transaction_id': transaction_id})

    except Exception as e:
        return JsonResponse({'error': f'A server error occurred: {str(e)}'}, status=500)
    
    
# === Full Views (Implemented) ===

@login_required
def configuration_view(request):
    family, _, _ = get_family_context(request.user)
    if not family:
        return redirect('dashboard') 

    config, created = FamilyConfiguration.objects.get_or_create(family=family)
    
    if request.method == 'POST':
        form = FamilyConfigurationForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Settings saved successfully.')
            return redirect('configuration')
    else:
        form = FamilyConfigurationForm(instance=config)

    # Context for base.html
    query_period = request.GET.get('period')
    start_date, _, _ = get_current_period_dates(family, query_period)
    
    context = {
        'form': form
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/configurations.html', context)

@login_required
def create_flow_group_view(request):
    family, current_member, family_members = get_family_context(request.user)
    if not family:
        return redirect('dashboard')

    if request.method == 'POST':
        form = FlowGroupForm(request.POST)
        if form.is_valid():
            flow_group = form.save(commit=False)
            flow_group.family = family
            flow_group.owner = request.user
            flow_group.save()
            messages.success(request, f"Flow Group '{flow_group.name}' created.")
            # Redirect to the edit page of the new group
            return redirect('edit_flow_group', group_id=flow_group.id)
    else:
        form = FlowGroupForm()

    # Context for base.html
    query_period = request.GET.get('period')
    start_date, _, _ = get_current_period_dates(family, query_period)

    context = {
        'form': form,
        'is_new': True,
        'family_members': family_members,
        'current_member': current_member,
        'today_date': timezone.localdate().strftime('%Y-%m-%d'),
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/FlowGroup.html', context)

@login_required
def edit_flow_group_view(request, group_id):
    family, current_member, family_members = get_family_context(request.user)
    if not family:
        return redirect('dashboard')
        
    group = get_object_or_404(FlowGroup, id=group_id, family=family)
    
    if request.method == 'POST':
        form = FlowGroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            messages.success(request, f"Flow Group '{group.name}' updated.")
            return redirect('edit_flow_group', group_id=group.id) # Redirect back to same page
    else:
        form = FlowGroupForm(instance=group)

    # Get transactions for this group
    transactions = Transaction.objects.filter(flow_group=group).select_related('member__user').order_by('order', '-date')

    # Context for base.html
    query_period = request.GET.get('period')
    start_date, _, _ = get_current_period_dates(family, query_period)

    context = {
        'form': form,
        'is_new': False,
        'flow_group': group, # FIX: Match template variable
        'transactions': transactions,
        'family_members': family_members,
        'current_member': current_member,
        'today_date': timezone.localdate().strftime('%Y-%m-%d'),
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/FlowGroup.html', context)

@login_required
def members_view(request):
    family, current_member, family_members = get_family_context(request.user)
    if not family:
        return redirect('dashboard')

    # TODO: Implement POST logic for adding member
    
    # Context for base.html
    query_period = request.GET.get('period')
    start_date, _, _ = get_current_period_dates(family, query_period)

    context = {
        'family_members': family_members,
        'add_member_form': NewUserAndMemberForm(), # FIX: Use the correct form
        'is_admin': current_member.role == 'ADMIN' 
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/members.html', context)

@login_required
def investments_view(request):
    family, _, _ = get_family_context(request.user)
    if not family:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = InvestmentForm(request.POST)
        if form.is_valid():
            investment = form.save(commit=False)
            investment.family = family
            investment.save()
            messages.success(request, 'Investment added.')
            return redirect('investments')
    else:
        form = InvestmentForm()

    investments = Investment.objects.filter(family=family).order_by('name')
    
    # Context for base.html
    query_period = request.GET.get('period')
    start_date, _, _ = get_current_period_dates(family, query_period)
    
    context = {
        'investment_form': form,
        'family_investments': investments
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/invest.html', context)

# --- Other Placeholder Views ---

@login_required
def add_receipt_view(request):
    # This should probably open the 'Income' flow group in the edit view
    family, _, _ = get_family_context(request.user)
    income_group = get_default_income_flow_group(family, request.user)
    return redirect('edit_flow_group', group_id=income_group.id)

@login_required
def add_member_view(request):
    # This logic should be (and is) handled in members_view
    return redirect('members')

@login_required
def remove_member_view(request, member_id):
    return HttpResponse(f"Remove Member View Placeholder for ID: {member_id}")

@login_required
@require_POST 
def investment_add_view(request):
    # This logic is handled in investments_view
    return redirect('investments')