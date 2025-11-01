# finances/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Max, Q
from django.db import transaction as db_transaction
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponse
from django.views.decorators.http import require_POST 
from django.contrib.auth import get_user_model 
from django.contrib import messages 
from django.utils import timezone
import json
from datetime import datetime as dt_datetime 
from decimal import Decimal

from .models import EXPENSE_MAIN
from .utils import get_available_periods

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
        defaults={'name': 'Income (Default)', 'budgeted_amount': Decimal('0.00'), 'owner': user} #-- removed - Any need from any owver
    )
    return income_group

# === Utility Wrapper for Period Context ===
def get_base_template_context(family, query_period, start_date):
    """
    Gets the context required by base.html (period selector with current period label).
    """
    # Get available periods
    available_periods = get_available_periods(family)
    
    # Determine current period label
    current_period_label = None
    for period in available_periods:
        if period['is_current']:
            current_period_label = period['label']
            break
    
    return {
        'available_periods': available_periods,
        'current_period_label': current_period_label
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
    
    # Calculate estimated (all transactions) and spent (realized only) for expense groups
    expense_groups = FlowGroup.objects.filter(
        expense_group_q,
        family=family,
    ).annotate(
        # Estimated: sum all transactions (realized or not) within period
        total_estimated=Sum(
            'transactions__amount',
            filter=Q(transactions__date__range=(start_date, end_date))
        ),
        # Spent: sum only realized transactions
        total_spent=Sum(
            'transactions__amount',
            filter=Q(transactions__date__range=(start_date, end_date), transactions__realized=True)
        )
    ).order_by('order', 'name')
    
    budgeted_expense = Decimal(0.00)
    for group in expense_groups:
        group.total_estimated = group.total_estimated if group.total_estimated is not None else Decimal('0.00')
        group.total_spent = group.total_spent if group.total_spent is not None else Decimal('0.00')
        # Check if estimated exceeds budget
        group.budget_warning = group.total_estimated > group.budgeted_amount
        group.total_estimated = group.total_estimated if group.total_estimated > group.budgeted_amount else group.budgeted_amount
        budgeted_expense = group.total_estimated + budgeted_expense

    income_group = get_default_income_flow_group(family, request.user)
    
    # Get income transactions ordered by date (most recent first)
    recent_income_transactions = Transaction.objects.filter(
        flow_group=income_group,
        date__range=(start_date, end_date)
    ).select_related('member__user').order_by('-date', 'order')    
    
    # Pass income group ID to template for AJAX calls
    income_flow_group_id = income_group.id
    
    expense_filter_budget = Q(group_type__in=FLOW_TYPE_EXPENSE)
    
    # Calculate summary totals
    summary_totals = FlowGroup.objects.filter(family=family).aggregate(
        # Budgeted income: sum all income transactions (realized or not)
        total_budgeted_income=Sum(
            'transactions__amount', 
            filter=Q(group_type=FLOW_TYPE_INCOME, transactions__date__range=(start_date, end_date))
        ),
        # Budgeted expense: use the estimated calculation (all transactions)
        total_budgeted_expense=Sum(
            'transactions__amount',
            filter=Q(group_type__in=FLOW_TYPE_EXPENSE, transactions__date__range=(start_date, end_date))
        ),
        # Realized income: sum only realized income transactions
        total_realized_income=Sum(
            'transactions__amount', 
            filter=Q(group_type=FLOW_TYPE_INCOME, transactions__date__range=(start_date, end_date), transactions__realized=True)
        ),
        # Realized expense: sum only realized expense transactions
        total_realized_expense=Sum(
            'transactions__amount', 
            filter=Q(group_type__in=FLOW_TYPE_EXPENSE, transactions__date__range=(start_date, end_date), transactions__realized=True)
        ),
    )
    
    
    budgeted_income = summary_totals.get('total_budgeted_income') or Decimal('0.00')
    budgeted_expense = budgeted_expense #See group.estimated calc section above
    realized_income = summary_totals.get('total_realized_income') or Decimal('0.00')
    realized_expense = summary_totals.get('total_realized_expense') or Decimal('0.00')    
    
    summary_totals['total_budgeted_expense'] = budgeted_expense
    summary_totals['estimated_result'] = budgeted_income - budgeted_expense
    summary_totals['realized_result'] = realized_income - realized_expense


    context = {
        'start_date': start_date,
        'end_date': end_date,
        'current_period_label': current_period_label,
        'expense_groups': expense_groups,
        'recent_income_transactions': recent_income_transactions,
        'income_flow_group_id': income_flow_group_id,
        'family_members': family_members,
        'current_member': current_member,
        'today_date': timezone.localdate().strftime('%Y-%m-%d'),
        'summary_totals': summary_totals,
    }
    
    # Add base.html context
    context.update(get_base_template_context(family, query_period, start_date))
    
    return render(request, 'finances/dashboard.html', context)


# === AJAX Endpoints ===

# finances/views.py

@login_required
@require_POST
@db_transaction.atomic
def save_flow_item_ajax(request):
    """
    Handles AJAX request to save or update a Transaction.
    This view matches the JS in FlowGroup.html and is adapted 
    for the Income items in dashboard.html.
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
        member_id = data.get('member_id') # This might be None from dashboard
        realized = data.get('realized', False)
        
        # Basic validation for fields that must always be present
        if not all([flow_group_id, description, amount_str, date_str]):
            return JsonResponse({'error': 'Missing required fields: flow_group, description, amount, or date.'}, status=400)
            
        amount = Decimal(amount_str)
        date = dt_datetime.strptime(date_str, '%Y-%m-%d').date()

        flow_group = get_object_or_404(FlowGroup, id=flow_group_id, family=family)

        if transaction_id and transaction_id != '0' and transaction_id is not None:
            # --- This is an UPDATE ---
            transaction = get_object_or_404(Transaction, id=transaction_id, flow_group=flow_group)
            
            # Only update member if member_id was EXPLICITLY provided
            # This prevents updates from dashboard (which send no member_id) from failing
            if member_id:
                member = get_object_or_404(FamilyMember, id=member_id, family=family)
                transaction.member = member
        
        else:
            # --- This is a CREATE ---
            max_order = Transaction.objects.filter(flow_group=flow_group).aggregate(max_order=Max('order'))['max_order']
            new_order = (max_order or 0) + 1
            transaction = Transaction(
                flow_group=flow_group,
                order=new_order
            )
            
            # For CREATE, member_id is required. 
            # Default to current_member if not provided (e.g., from dashboard)
            if member_id:
                member = get_object_or_404(FamilyMember, id=member_id, family=family)
            else:
                member = current_member # Default to the logged-in user
            
            transaction.member = member

        # Apply updates for both Create and Update
        transaction.description = description
        transaction.amount = abs(amount) 
        transaction.date = date
        transaction.realized = realized  # Save realized status
        transaction.save()

        # Return the saved state, ensuring member data is from the transaction
        return JsonResponse({
            'status': 'success',
            'transaction_id': transaction.id,
            'description': transaction.description,
            'amount': str(transaction.amount),
            'date': transaction.date.strftime('%Y-%m-%d'),
            'member_id': transaction.member.id,
            'member_name': transaction.member.user.username,
            'realized': transaction.realized,
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
            flow_group.group_type = EXPENSE_MAIN  # Always set to EXPENSE_MAIN
            flow_group.save()
            messages.success(request, f"Flow Group '{flow_group.name}' created.")
            return redirect('edit_flow_group', group_id=flow_group.id)
    else:
        form = FlowGroupForm()

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
            return redirect('edit_flow_group', group_id=group.id)
    else:
        form = FlowGroupForm(instance=group)

    # Get transactions for this group
    transactions = Transaction.objects.filter(flow_group=group).select_related('member__user').order_by('order', '-date')
    
    # Calculate total estimated for budget warning
    query_period = request.GET.get('period')
    start_date, end_date, _ = get_current_period_dates(family, query_period)
    
    total_estimated = transactions.filter(date__range=(start_date, end_date)).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    budget_warning = total_estimated > group.budgeted_amount if group.budgeted_amount else False

    context = {
        'form': form,
        'is_new': False,
        'flow_group': group,
        'transactions': transactions,
        'family_members': family_members,
        'current_member': current_member,
        'today_date': timezone.localdate().strftime('%Y-%m-%d'),
        'total_estimated': total_estimated,
        'budget_warning': budget_warning,
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
        'add_member_form': NewUserAndMemberForm(),
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

# === Delete Flow Group View ===
@login_required
@require_POST
@db_transaction.atomic
def delete_flow_group_view(request, group_id):
    """
    Deletes a FlowGroup and all its transactions for the current period only.
    """
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return JsonResponse({'error': 'User is not associated with a family.'}, status=403)
    
    try:
        # Get the flow group
        flow_group = get_object_or_404(FlowGroup, id=group_id, family=family)
        
        # Get current period dates
        query_period = request.GET.get('period')
        start_date, end_date, _ = get_current_period_dates(family, query_period)
        
        # Delete only transactions within the current period
        transactions_deleted = Transaction.objects.filter(
            flow_group=flow_group,
            date__range=(start_date, end_date)
        ).delete()
        
        # Check if there are any transactions left in other periods
        remaining_transactions = Transaction.objects.filter(flow_group=flow_group).exists()
        
        if not remaining_transactions:
            # No transactions in any period - safe to delete the group
            flow_group.delete()
            message = f"Flow Group '{flow_group.name}' and all its data have been deleted."
        else:
            # Transactions exist in other periods - keep the group
            message = f"All transactions for the current period have been deleted. Group '{flow_group.name}' still contains data from other periods."
        
        return JsonResponse({
            'status': 'success',
            'message': message,
            'transactions_deleted': transactions_deleted[0] if transactions_deleted else 0
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# --- Other Placeholder Views ---

@login_required
def add_receipt_view(request):
    # This should probably open the 'Income' flow group in the edit view
    family, _, _ = get_family_context(request.user)
    income_group = get_default_income_flow_group(family, request.user)
    return redirect('edit_flow_group', group_id=income_group.id)

@login_required
@require_POST
@db_transaction.atomic
def add_member_view(request):
    """
    Handles adding a new family member.
    """
    family, current_member, _ = get_family_context(request.user)
    if not family:
        messages.error(request, 'User is not associated with a family.')
        return redirect('members')
    
    # Check if user is admin
    if current_member.role != 'ADMIN':
        messages.error(request, 'Only admins can add new members.')
        return redirect('members')
    
    form = NewUserAndMemberForm(request.POST)
    
    if form.is_valid():
        try:
            # Create new user
            UserModel = get_user_model()
            new_user = UserModel.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data.get('email', ''),
                password=form.cleaned_data['password']
            )
            
            # Create family member
            FamilyMember.objects.create(
                user=new_user,
                family=family,
                role=form.cleaned_data['role']
            )
            
            messages.success(request, f"Member '{new_user.username}' added successfully!")
            return redirect('members')
            
        except Exception as e:
            messages.error(request, f"Error creating member: {str(e)}")
            return redirect('members')
    else:
        # Form has errors
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
        return redirect('members')

# === AJAX endpoint for periods (optional, for dynamic loading) ===
@login_required
def get_periods_ajax(request):
    """
    Returns available periods as JSON for AJAX requests.
    """
    family, _, _ = get_family_context(request.user)
    if not family:
        return JsonResponse({'error': 'User is not associated with a family.'}, status=403)
    
    periods = get_available_periods(family)
    
    # Convert to JSON-serializable format
    periods_data = [{
        'label': p['label'],
        'value': p['value'],
        'is_current': p['is_current'],
        'has_data': p['has_data']
    } for p in periods]
    
    return JsonResponse({'periods': periods_data})

@login_required
def remove_member_view(request, member_id):
    return HttpResponse(f"Remove Member View Placeholder for ID: {member_id}")

@login_required
@require_POST 
def investment_add_view(request):
    # This logic is handled in investments_view
    return redirect('investments')