# finances/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Max, Q
from django.db import transaction as db_transaction
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth import get_user_model, logout as auth_logout
from django.contrib import messages 
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
from .utils import get_current_period_dates, get_available_periods

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
def get_default_income_flow_group(family, user, period_start_date):
    """Retrieves or creates the default income FlowGroup for the family and period."""
    income_group, created = FlowGroup.objects.get_or_create(
        family=family,
        group_type=FLOW_TYPE_INCOME,
        period_start_date=period_start_date,
        defaults={'name': 'Income (Default)', 'budgeted_amount': Decimal('0.00'), 'owner': user}
    )
    return income_group

# === Utility Wrapper for Period Context ===
def get_base_template_context(family, query_period, start_date):
    """
    Gets the context required by base.html (period selector with current period label).
    """
    # Get available periods
    available_periods = get_available_periods(family)
    
    # Find current period label based on query_period or current date
    current_period_label = None
    current_period_value = query_period if query_period else start_date.strftime("%Y-%m-%d")
    
    for period in available_periods:
        if period['value'] == current_period_value:
            period['is_current'] = True
            current_period_label = period['label']
        else:
            period['is_current'] = False
    
    # If no match found, use the first period (current)
    if not current_period_label and available_periods:
        available_periods[0]['is_current'] = True
        current_period_label = available_periods[0]['label']
    
    return {
        'available_periods': available_periods,
        'current_period_label': current_period_label,
        'selected_period': current_period_value
    }

# === Utility Function for Default Date ===
def get_default_date_for_period(start_date, end_date):
    """
    Returns the appropriate default date for data entry.
    If the period includes today, return today.
    If it's a past period, return the start date.
    If it's a future period, return the start date.
    """
    today = timezone.localdate()
    
    if start_date <= today <= end_date:
        # Current period - use today
        return today
    else:
        # Past or future period - use start date
        return start_date

# === Core Views ===

@login_required
def dashboard_view(request):
    family, current_member, family_members = get_family_context(request.user)
    if not family:
        return render(request, 'finances/setup.html') 

    query_period = request.GET.get('period')
    start_date, end_date, current_period_label = get_current_period_dates(family, query_period)
    
    expense_group_q = Q(group_type=EXPENSE_MAIN) | Q(group_type=EXPENSE_SECONDARY)
    
    # IMPORTANT: Filter FlowGroups by period_start_date
    expense_groups = FlowGroup.objects.filter(
        expense_group_q,
        family=family,
        period_start_date=start_date  # Filter by period
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

    income_group = get_default_income_flow_group(family, request.user, start_date)
    
    # Get income transactions ordered by date (most recent first)
    recent_income_transactions = Transaction.objects.filter(
        flow_group=income_group,
        date__range=(start_date, end_date)
    ).select_related('member__user').order_by('-date', 'order')    
    
    # Pass income group ID to template for AJAX calls
    income_flow_group_id = income_group.id
    
    # Calculate summary totals - filter by period
    summary_totals = FlowGroup.objects.filter(
        family=family,
        period_start_date=start_date  # Filter by period
    ).aggregate(
        # Budgeted income: sum all income transactions (realized or not)
        total_budgeted_income=Sum(
            'transactions__amount', 
            filter=Q(group_type=FLOW_TYPE_INCOME, transactions__date__range=(start_date, end_date))
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
    realized_income = summary_totals.get('total_realized_income') or Decimal('0.00')
    realized_expense = summary_totals.get('total_realized_expense') or Decimal('0.00')    
    
    summary_totals['total_budgeted_expense'] = budgeted_expense
    summary_totals['estimated_result'] = budgeted_income - budgeted_expense
    summary_totals['realized_result'] = realized_income - realized_expense

    # Get default date for this period
    default_date = get_default_date_for_period(start_date, end_date)

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'current_period_label': current_period_label,
        'expense_groups': expense_groups,
        'recent_income_transactions': recent_income_transactions,
        'income_flow_group_id': income_flow_group_id,
        'family_members': family_members,
        'current_member': current_member,
        'today_date': default_date.strftime('%Y-%m-%d'),
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
        member_id = data.get('member_id')
        realized = data.get('realized', False)
        
        # Basic validation
        if not all([flow_group_id, description, amount_str, date_str]):
            return JsonResponse({'error': 'Missing required fields.'}, status=400)
            
        amount = Decimal(amount_str)
        date = dt_datetime.strptime(date_str, '%Y-%m-%d').date()

        flow_group = get_object_or_404(FlowGroup, id=flow_group_id, family=family)

        if transaction_id and transaction_id != '0' and transaction_id is not None:
            transaction = get_object_or_404(Transaction, id=transaction_id, flow_group=flow_group)
            if member_id:
                member = get_object_or_404(FamilyMember, id=member_id, family=family)
                transaction.member = member
        else:
            max_order = Transaction.objects.filter(flow_group=flow_group).aggregate(max_order=Max('order'))['max_order']
            new_order = (max_order or 0) + 1
            transaction = Transaction(
                flow_group=flow_group,
                order=new_order
            )
            
            if member_id:
                member = get_object_or_404(FamilyMember, id=member_id, family=family)
            else:
                member = current_member
            
            transaction.member = member

        transaction.description = description
        transaction.amount = abs(amount) 
        transaction.date = date
        transaction.realized = realized
        transaction.save()

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


# === Delete Flow Group View ===
@login_required
@require_POST
@db_transaction.atomic
def delete_flow_group_view(request, group_id):
    """
    Deletes a FlowGroup and all its transactions.
    """
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return JsonResponse({'error': 'User is not associated with a family.'}, status=403)
    
    try:
        flow_group = get_object_or_404(FlowGroup, id=group_id, family=family)
        group_name = flow_group.name
        
        # Delete the group (CASCADE will delete all transactions)
        flow_group.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': f"Flow Group '{group_name}' and all its data have been deleted."
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# === Logout View ===
@require_POST
def logout_view(request):
    """
    Logs out the user and redirects to logout success page.
    Only accepts POST requests for security.
    """
    auth_logout(request)
    return redirect('logout_success')


# === Logout Success View ===
def logout_success_view(request):
    """
    Shows logout success page (no authentication required).
    """
    return render(request, 'finances/logged_out.html')


# === User Profile View ===
@login_required
def user_profile_view(request):
    """
    View and edit user profile (username, email, password).
    """
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return redirect('dashboard')
    
    query_period = request.GET.get('period')
    start_date, end_date, _ = get_current_period_dates(family, query_period)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_profile':
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()
            
            if username:
                UserModel = get_user_model()
                # Check if username is taken by another user
                if UserModel.objects.filter(username=username).exclude(id=request.user.id).exists():
                    messages.error(request, 'This username is already taken.')
                else:
                    request.user.username = username
                    request.user.email = email
                    request.user.save()
                    messages.success(request, 'Profile updated successfully.')
            else:
                messages.error(request, 'Username cannot be empty.')
        
        elif action == 'change_password':
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            if not request.user.check_password(current_password):
                messages.error(request, 'Current password is incorrect.')
            elif len(new_password) < 6:
                messages.error(request, 'New password must be at least 6 characters long.')
            elif new_password != confirm_password:
                messages.error(request, 'New passwords do not match.')
            else:
                request.user.set_password(new_password)
                request.user.save()
                # Re-login user to maintain session
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Password changed successfully.')
        
        # Preserve period in redirect
        redirect_url = f"?period={query_period}" if query_period else ""
        return redirect(f"/profile/{redirect_url}")
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'current_member': current_member,
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/profile.html', context)


# === Configuration View ===
@login_required
def configuration_view(request):
    family, _, _ = get_family_context(request.user)
    if not family:
        return redirect('dashboard') 

    config, created = FamilyConfiguration.objects.get_or_create(family=family)
    
    query_period = request.GET.get('period')
    
    if request.method == 'POST':
        form = FamilyConfigurationForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Settings saved successfully.')
            # Preserve period in redirect
            if query_period:
                return redirect(f"{request.path}?period={query_period}")
            return redirect('configuration')
    else:
        form = FamilyConfigurationForm(instance=config)

    start_date, end_date, _ = get_current_period_dates(family, query_period)
    
    context = {
        'form': form,
        'start_date': start_date,
        'end_date': end_date,
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/configurations.html', context)


@login_required
def create_flow_group_view(request):
    family, current_member, family_members = get_family_context(request.user)
    if not family:
        return redirect('dashboard')

    # Get period from query parameter (critical for maintaining selected period)
    query_period = request.GET.get('period') or request.POST.get('period')
    start_date, end_date, _ = get_current_period_dates(family, query_period)

    if request.method == 'POST':
        form = FlowGroupForm(request.POST)
        if form.is_valid():
            flow_group = form.save(commit=False)
            flow_group.family = family
            flow_group.owner = request.user
            flow_group.group_type = EXPENSE_MAIN
            # CRITICAL: Use the period from query/POST parameter, not current date
            flow_group.period_start_date = start_date
            flow_group.save()
            messages.success(request, f"Flow Group '{flow_group.name}' created for period starting {start_date.strftime('%B %d, %Y')}.")
            # Preserve period in redirect
            redirect_url = f"?period={start_date.strftime('%Y-%m-%d')}"
            return redirect(f"/flow-group/{flow_group.id}/edit/{redirect_url}")
    else:
        form = FlowGroupForm()

    # Get default date for this period
    default_date = get_default_date_for_period(start_date, end_date)

    context = {
        'form': form,
        'is_new': True,
        'family_members': family_members,
        'current_member': current_member,
        'today_date': default_date.strftime('%Y-%m-%d'),
        'start_date': start_date,
        'end_date': end_date,
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/FlowGroup.html', context)


@login_required
def edit_flow_group_view(request, group_id):
    family, current_member, family_members = get_family_context(request.user)
    if not family:
        return redirect('dashboard')
        
    group = get_object_or_404(FlowGroup, id=group_id, family=family)
    
    # Get period from query parameter, or use the group's period
    query_period = request.GET.get('period')
    if not query_period:
        # Use the FlowGroup's period_start_date as the default
        query_period = group.period_start_date.strftime('%Y-%m-%d')
    
    start_date, end_date, _ = get_current_period_dates(family, query_period)
    
    if request.method == 'POST':
        form = FlowGroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            messages.success(request, f"Flow Group '{group.name}' updated.")
            # Preserve period in redirect
            redirect_url = f"?period={query_period}" if query_period else ""
            return redirect(f"/flow-group/{group_id}/edit/{redirect_url}")
    else:
        form = FlowGroupForm(instance=group)

    transactions = Transaction.objects.filter(flow_group=group).select_related('member__user').order_by('order', '-date')
    
    total_estimated = transactions.filter(date__range=(start_date, end_date)).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    budget_warning = total_estimated > group.budgeted_amount if group.budgeted_amount else False

    # Get default date for this period
    default_date = get_default_date_for_period(start_date, end_date)

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
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/FlowGroup.html', context)


@login_required
def members_view(request):
    family, current_member, family_members = get_family_context(request.user)
    if not family:
        return redirect('dashboard')
    
    query_period = request.GET.get('period')
    start_date, end_date, _ = get_current_period_dates(family, query_period)

    context = {
        'family_members': family_members,
        'add_member_form': NewUserAndMemberForm(),
        'is_admin': current_member.role == 'ADMIN',
        'start_date': start_date,
        'end_date': end_date,
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/members.html', context)


@login_required
@require_POST
@db_transaction.atomic
def add_member_view(request):
    """Handles adding a new family member."""
    family, current_member, _ = get_family_context(request.user)
    if not family:
        messages.error(request, 'User is not associated with a family.')
        return redirect('members')
    
    if current_member.role != 'ADMIN':
        messages.error(request, 'Only admins can add new members.')
        return redirect('members')
    
    form = NewUserAndMemberForm(request.POST)
    
    # Preserve period in redirect
    query_period = request.GET.get('period')
    redirect_url = f"?period={query_period}" if query_period else ""
    
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
            return redirect(f"/members/{redirect_url}")
            
        except Exception as e:
            messages.error(request, f"Error creating member: {str(e)}")
            return redirect(f"/members/{redirect_url}")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
        return redirect(f"/members/{redirect_url}")


@login_required
def edit_member_view(request, member_id):
    """Edit member details."""
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return redirect('dashboard')
    
    if current_member.role != 'ADMIN':
        messages.error(request, 'Only admins can edit members.')
        return redirect('members')
    
    member = get_object_or_404(FamilyMember, id=member_id, family=family)
    
    # Preserve period in redirect
    query_period = request.GET.get('period')
    redirect_url = f"?period={query_period}" if query_period else ""
    
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
        
        return redirect(f"/members/{redirect_url}")
    
    return redirect(f"/members/{redirect_url}")


@login_required
@require_POST
def remove_member_view(request, member_id):
    """Removes a member from the family."""
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
    
    # Preserve period in redirect
    query_period = request.GET.get('period')
    redirect_url = f"?period={query_period}" if query_period else ""
    return redirect(f"/members/{redirect_url}")


@login_required
def investments_view(request):
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
            # Preserve period in redirect
            redirect_url = f"?period={query_period}" if query_period else ""
            return redirect(f"/investments/{redirect_url}")
    else:
        form = InvestmentForm()

    investments = Investment.objects.filter(family=family).order_by('name')
    
    start_date, end_date, _ = get_current_period_dates(family, query_period)
    
    context = {
        'investment_form': form,
        'family_investments': investments,
        'start_date': start_date,
        'end_date': end_date,
    }
    context.update(get_base_template_context(family, query_period, start_date))
    return render(request, 'finances/invest.html', context)


@login_required
def add_receipt_view(request):
    family, _, _ = get_family_context(request.user)
    query_period = request.GET.get('period')
    start_date, _, _ = get_current_period_dates(family, query_period)
    income_group = get_default_income_flow_group(family, request.user, start_date)
    # Preserve period in redirect
    redirect_url = f"?period={query_period}" if query_period else ""
    return redirect(f"/flow-group/{income_group.id}/edit/{redirect_url}")

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
@require_POST 
def investment_add_view(request):
    query_period = request.GET.get('period')
    redirect_url = f"?period={query_period}" if query_period else ""
    return redirect(f"/investments/{redirect_url}")
