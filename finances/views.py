VERSION = "1.0-alpha"

from django.core.management import call_command
import io

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Max, Q
from django.db import transaction as db_transaction
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth import get_user_model, logout as auth_logout, login
from django.contrib import messages 
from django.utils import timezone
import json
from datetime import datetime as dt_datetime 
from decimal import Decimal
from .forms import InitialSetupForm  
from django.db.utils import OperationalError

# Import Models
from .models import (
    Family, FamilyMember, FlowGroup, Transaction, Investment, FamilyConfiguration, ClosedPeriod,
    FLOW_TYPE_INCOME, EXPENSE_MAIN, EXPENSE_SECONDARY, FLOW_TYPE_EXPENSE 
)
from .utils import (
    get_current_period_dates, 
    get_available_periods,
    check_period_change_impact, 
    close_current_period,
    copy_flow_groups_to_new_period,
    copy_previous_period_data,
    current_period_has_data
)

# Import Forms
from .forms import (
    FamilyConfigurationForm, FlowGroupForm, InvestmentForm, 
    AddMemberForm, NewUserAndMemberForm
)

# Import Utility Functions
from .utils import get_current_period_dates, get_available_periods



def initial_setup_view(request):
    """
    Initial setup view for first-time installation.
    Creates the first admin user, family, and configuration.
    Also handles database creation and migrations if needed.
    """
    
    # === STEP 1: Ensure database and tables exist ===
    try:
        UserModel = get_user_model()
        # Try to check if users exist
        users_exist = UserModel.objects.exists()
        
        # If users exist, redirect appropriately
        if users_exist:
            if request.user.is_authenticated:
                return redirect('dashboard')
            return redirect('auth_login')
            
    except OperationalError as e:
        # Database tables don't exist - need to run migrations
        if request.method != 'POST':
            # Show a loading message and run migrations
            context = {
                'needs_migration': True,
                'error_message': 'Database setup required. Running migrations...'
            }
            
            # Run migrations in the background
            try:
                # Capture output
                out = io.StringIO()
                
                # Run migrate command
                call_command('migrate', '--noinput', stdout=out, stderr=out)
                
                migration_output = out.getvalue()
                
                # Add success message
                context['migration_success'] = True
                context['migration_output'] = migration_output
                
            except Exception as migration_error:
                context['migration_error'] = str(migration_error)
            
            # Re-render the setup page (will now work with DB created)
            return render(request, 'finances/setup.html', {'form': InitialSetupForm(), **context})
    
    except Exception as e:
        # Other database errors
        messages.error(request, f"Database error: {str(e)}")
        context = {
            'form': InitialSetupForm(),
            'database_error': str(e)
        }
        return render(request, 'finances/setup.html', context)
    
    # === STEP 2: Handle form submission ===
    if request.method == 'POST':
        form = InitialSetupForm(request.POST)
        
        if form.is_valid():
            try:
                with db_transaction.atomic():
                    # 1. Create the admin user
                    UserModel = get_user_model()
                    admin_user = UserModel.objects.create_user(
                        username=form.cleaned_data['username'],
                        email=form.cleaned_data.get('email', ''),
                        password=form.cleaned_data['password']
                    )
                    
                    # 2. Create the family
                    family = Family.objects.create(
                        name=form.cleaned_data['family_name']
                    )
                    
                    # 3. Create the family member (admin)
                    family_member = FamilyMember.objects.create(
                        user=admin_user,
                        family=family,
                        role='ADMIN'
                    )
                    
                    # 4. Create the family configuration
                    base_date = form.cleaned_data.get('base_date')
                    if not base_date:
                        base_date = timezone.localdate()
                    
                    config = FamilyConfiguration.objects.create(
                        family=family,
                        starting_day=form.cleaned_data['starting_day'],
                        period_type=form.cleaned_data['period_type'],
                        base_date=base_date
                    )
                    
                    # 5. Log the user in
                    login(request, admin_user)
                    
                    # 6. Success message and redirect
                    messages.success(
                        request,
                        f"Welcome to WIMM! Your family '{family.name}' has been created successfully."
                    )
                    return redirect('dashboard')
                    
            except Exception as e:
                messages.error(
                    request,
                    f"An error occurred during setup: {str(e)}. Please try again."
                )
        else:
            # Form has validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        # GET request - show empty form
        # Set default base_date to today
        initial_data = {
            'base_date': timezone.localdate(),
            'starting_day': 1,
            'period_type': 'M'
        }
        form = InitialSetupForm(initial=initial_data)
    
    return render(request, 'finances/setup.html', {'form': form})


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

# === Utility function to check FlowGroup access ===
def can_access_flow_group(flow_group, family_member):
    """
    Determines if a family member can access a FlowGroup based on sharing rules.
    
    Rules:
    - Owner can always access
    - Admins can ALWAYS access ALL FlowGroups (to fix sharing errors)
    - Parents can access shared groups IF they are in assigned_members
    - Children can access Kids groups they are assigned to
    - Children can access Income FlowGroups (to add manual income)
    """
    # Owner always has access
    if flow_group.owner == family_member.user:
        return True
    
    # ADMINS HAVE ACCESS TO EVERYTHING
    if family_member.role == 'ADMIN':
        return True
    
    # Parents can access shared groups if assigned
    if family_member.role == 'PARENT':
        if flow_group.is_shared:
            # Check if member is in assigned_members
            if flow_group.assigned_members.filter(id=family_member.id).exists():
                return True
        # Kids groups are accessible to all Parents
        if flow_group.is_kids_group:
            return True
    
    # Children can access Kids groups they're assigned to
    if family_member.role == 'CHILD':
        if flow_group.is_kids_group and family_member in flow_group.assigned_children.all():
            return True
        # Children can also access Income FlowGroups to add manual income
        if flow_group.group_type == FLOW_TYPE_INCOME:
            return True
    
    return False

# === Get visible flow groups for dashboard (includes non-accessible for display only) ===
def get_visible_flow_groups_for_dashboard(family, family_member, period_start_date, group_type_filter=None):
    """
    Returns FlowGroups visible in the dashboard for the given family member.
    
    For PARENT/ADMIN: Shows ALL expense groups (owned, shared, and non-accessible)
    For CHILD: Shows only Kids groups assigned to them
    
    Returns tuple: (accessible_groups, display_only_groups)
    """
    base_query = FlowGroup.objects.filter(
        family=family,
        period_start_date=period_start_date
    )
    
    if group_type_filter:
        base_query = base_query.filter(group_type__in=group_type_filter)
    
    if family_member.role == 'CHILD':
        # Children see only Kids groups they're assigned to (all accessible)
        accessible_groups = base_query.filter(
            Q(is_kids_group=True, assigned_children=family_member)
        ).distinct()
        display_only_groups = FlowGroup.objects.none()
    else:
        # Parents/Admins see ALL expense groups
        all_groups = base_query.all()
        
        # Separate accessible from display-only
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

# === NEW: Get visible flow groups for editing ===
def get_visible_flow_groups(family, family_member, period_start_date, group_type_filter=None):
    """
    Returns FlowGroups visible to the given family member for the specified period.
    
    Visibility rules:
    - Own groups (always visible)
    - Shared groups (visible to assigned Admins/Parents only)
    - Kids groups (visible to assigned children, and to all Admins/Parents)
    - Admins can see ALL groups
    """
    base_query = FlowGroup.objects.filter(
        family=family,
        period_start_date=period_start_date
    )
    
    if group_type_filter:
        base_query = base_query.filter(group_type__in=group_type_filter)
    
    if family_member.role == 'CHILD':
        # Children see only Kids groups they're assigned to
        visible_groups = base_query.filter(
            Q(is_kids_group=True, assigned_children=family_member)
        )
    elif family_member.role == 'ADMIN':
        # Admins see ALL groups
        visible_groups = base_query.all()
    else:
        # Parents see:
        # 1. Their own groups (non-shared)
        # 2. Shared groups they're assigned to
        # 3. All Kids groups
        visible_groups = base_query.filter(
            Q(owner=family_member.user) |  # Own groups
            Q(is_shared=True, assigned_members=family_member) |  # Shared groups (assigned)
            Q(is_kids_group=True)  # Kids groups (all)
        )
    
    return visible_groups.distinct()

# === Utility Wrapper for Period Context ===
def get_base_template_context(family, query_period, start_date):
    """
    Gets the context required by base.html (period selector with current period label).
    Adds VERSION to context.
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
        'selected_period': current_period_value,
        'app_version': VERSION,
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

# === NEW: Get periods history for bar chart ===
def get_periods_history(family, current_period_start):
    """
    Returns the last 12 periods with total expenses for bar chart.
    Includes dynamic bar colors based on income commitment %.
    Returns dict with 'labels', 'values', 'colors', 'avg_savings', and 'trend'.
    ONLY INCLUDES PERIODS WITH DATA.
    """
    available_periods = get_available_periods(family)
    
    # Get up to 12 most recent periods that have data
    periods_to_show = []
    savings_values = []
    
    for period in available_periods[:24]:  # Look at more periods to find 12 with data
        period_start = period['start_date']
        period_end = period['end_date']
        
        # Check if period has any transaction data
        has_data = Transaction.objects.filter(
            flow_group__family=family,
            date__range=(period_start, period_end)
        ).exists()
        
        # Skip periods without data
        if not has_data:
            continue
        
        # Calculate total realized expenses
        total_expenses = Transaction.objects.filter(
            flow_group__family=family,
            flow_group__group_type__in=FLOW_TYPE_EXPENSE,
            date__range=(period_start, period_end),
            realized=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Calculate total realized income
        total_income = Transaction.objects.filter(
            flow_group__family=family,
            flow_group__group_type=FLOW_TYPE_INCOME,
            date__range=(period_start, period_end),
            realized=True,
            is_child_manual_income=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Add Kids groups realized budgets to expenses
        kids_realized = FlowGroup.objects.filter(
            family=family,
            period_start_date=period_start,
            is_kids_group=True,
            realized=True
        ).aggregate(total=Sum('budgeted_amount'))['total'] or Decimal('0.00')
        
        total_expenses += kids_realized
        
        # Calculate commitment percentage
        commitment_pct = 0
        if total_income > 0:
            commitment_pct = float(total_expenses / total_income * 100)
        
        # Determine bar color based on commitment
        if commitment_pct >= 98:
            bar_color = 'rgb(239, 68, 68)'  # Red
        elif commitment_pct >= 90:
            bar_color = 'rgb(249, 115, 22)'  # Orange
        else:
            bar_color = 'rgb(134, 239, 172)'  # Light green
        
        # Calculate savings (income - expenses)
        savings = float(total_income - total_expenses)
        savings_values.append(savings)
        
        periods_to_show.append({
            'label': period['label'],
            'value': float(total_expenses),
            'color': bar_color,
            'savings': savings
        })
        
        # Stop if we have 12 periods
        if len(periods_to_show) >= 12:
            break
    
    # Reverse to show oldest to newest (left to right)
    periods_to_show.reverse()
    savings_values.reverse()
    
    # Calculate average savings
    avg_savings = sum(savings_values) / len(savings_values) if savings_values else 0
    
    # Calculate trend (compare first half vs second half)
    trend = 'stable'
    if len(periods_to_show) >= 6:
        half_point = len(periods_to_show) // 2
        first_half_avg = sum(p['value'] for p in periods_to_show[:half_point]) / half_point
        second_half_avg = sum(p['value'] for p in periods_to_show[half_point:]) / (len(periods_to_show) - half_point)
        
        # If second half is 5% or more higher, trend is up
        if second_half_avg > first_half_avg * 1.05:
            trend = 'up'
        # If second half is 5% or more lower, trend is down
        elif second_half_avg < first_half_avg * 0.95:
            trend = 'down'
    
    return {
        'labels': [p['label'] for p in periods_to_show],
        'values': [p['value'] for p in periods_to_show],
        'colors': [p['color'] for p in periods_to_show],
        'avg_savings': avg_savings,
        'trend': trend
    }

# === Core Views ===

@login_required
def dashboard_view(request):
    family, current_member, family_members = get_family_context(request.user)
    from decimal import Decimal, ROUND_DOWN
    if not family:
        return render(request, 'finances/setup.html') 

    query_period = request.GET.get('period')
    start_date, end_date, current_period_label = get_current_period_dates(family, query_period)
    
    # Get historical role for this period
    from .utils import get_member_role_for_period
    member_role_for_period = get_member_role_for_period(current_member, start_date)
    
    expense_group_q = Q(group_type=EXPENSE_MAIN) | Q(group_type=EXPENSE_SECONDARY)
    
    # Get visible expense groups based on HISTORICAL role
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
    
    # Annotate display-only groups (for Parents/Admins to see in dashboard)
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
    
    # Process accessible groups
    budgeted_expense = Decimal(0.00)
    for group in accessible_expense_groups:
        group.total_estimated = (group.total_estimated if group.total_estimated is not None else Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        group.total_spent = (group.total_spent if group.total_spent is not None else Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        group.is_accessible = True  # Mark as accessible
        
        # For Kids groups shown to Parents/Admins, calculate child expenses
        if group.is_kids_group and member_role_for_period in ['ADMIN', 'PARENT']:
            group.child_expenses = Transaction.objects.filter(
                flow_group=group,
                date__range=(start_date, end_date)
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            # Mark if this group was created by a child (owner is a child)
            group.is_child_group = False
            if group.owner:
                owner_member = FamilyMember.objects.filter(user=group.owner, family=family).first()
                if owner_member and owner_member.role == 'CHILD':
                    group.is_child_group = True
        
        # Check if estimated exceeds budget
        group.budget_warning = group.total_estimated > group.budgeted_amount
        group.total_estimated = group.total_estimated if group.total_estimated > group.budgeted_amount else group.budgeted_amount
        
        # Only add to budgeted_expense if it's NOT a child's own group
        is_child_own_group = False
        if group.owner:
            owner_member = FamilyMember.objects.filter(user=group.owner, family=family).first()
            if owner_member and owner_member.role == 'CHILD':
                is_child_own_group = True
        
        if not is_child_own_group:
            budgeted_expense = group.total_estimated + budgeted_expense

        
    
    # Process display-only groups (for Parents/Admins)
    for group in display_only_expense_groups:
        group.total_estimated = (group.total_estimated if group.total_estimated is not None else Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        group.total_spent = (group.total_spent if group.total_spent is not None else Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        group.is_accessible = False  # Mark as NOT accessible
        
        # Check if estimated exceeds budget
        group.budget_warning = group.total_estimated > group.budgeted_amount
        group.total_estimated = group.total_estimated if group.total_estimated > group.budgeted_amount else group.budgeted_amount
        
        # Add to budgeted_expense
        budgeted_expense = group.total_estimated + budgeted_expense
    
    # Combine accessible and display-only groups for template
    expense_groups = list(accessible_expense_groups) + list(display_only_expense_groups)

    # Income calculation differs based on HISTORICAL role
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
            kids_income_entries.append({
                'id': f'kids_{kids_group.id}',
                'description': kids_group.name,
                'amount': (kids_group.budgeted_amount).quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'date': start_date,
                'realized': kids_group.realized,
                'is_kids_income': True,
                'kids_group_id': kids_group.id,
                'member': current_member,
            })
            budgeted_income += kids_group.budgeted_amount
            if kids_group.realized:
                realized_income += kids_group.budgeted_amount
        
        income_group = get_default_income_flow_group(family, request.user, start_date)
        manual_income_transactions = Transaction.objects.filter(
            flow_group=income_group,
            date__range=(start_date, end_date),
            member=current_member,
            is_child_manual_income=True
        ).select_related('member__user').order_by('-date', 'order')
        
        for trans in manual_income_transactions:
            budgeted_income += trans.amount
            if trans.realized:
                realized_income += trans.amount
        
        recent_income_transactions = list(manual_income_transactions)
        income_flow_group_id = income_group.id
        context_kids_income = kids_income_entries

        realized_expense = Transaction.objects.filter(
            flow_group__in=accessible_expense_groups,
            date__range=(start_date, end_date),
            realized=True,
            is_child_expense=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')        
        
    else:
        # === PARENTS/ADMINS VIEW ===
        income_group = get_default_income_flow_group(family, request.user, start_date)
        
        recent_income_transactions = Transaction.objects.filter(
            flow_group=income_group,
            date__range=(start_date, end_date),
            is_child_manual_income=False
        ).select_related('member__user').order_by('-date', 'order')
        
        income_flow_group_id = income_group.id
        
        budgeted_income = Transaction.objects.filter(
            flow_group=income_group,
            date__range=(start_date, end_date),
            is_child_manual_income=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        realized_income = Transaction.objects.filter(
            flow_group=income_group,
            date__range=(start_date, end_date),
            realized=True,
            is_child_manual_income=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        kids_groups_realized_budget = FlowGroup.objects.filter(
            family=family,
            period_start_date=start_date,
            is_kids_group=True,
            realized=True
        ).aggregate(total=Sum('budgeted_amount'))['total'] or Decimal('0.00')
            
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
                    total = child_income.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                    realized_total = child_income.filter(realized=True).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                    
                    children_manual_income[child.id] = {
                        'member': child,
                        'total': total,
                        'realized_total': realized_total,
                        'transactions': list(child_income.values('description', 'amount', 'date', 'realized'))
                    }
        
        context_kids_income = []
        realized_expense = Transaction.objects.filter(
            flow_group__in=accessible_expense_groups,
            date__range=(start_date, end_date),
            realized=True,
            is_child_expense=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
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
        child_manual_income_total = Transaction.objects.filter(
            flow_group__group_type=FLOW_TYPE_INCOME,
            date__range=(start_date, end_date),
            member=current_member,
            is_child_manual_income=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        child_can_create_groups = child_manual_income_total > Decimal('0.00')

    # Get periods history for bar chart
    periods_history = get_periods_history(family, start_date)

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
    }
    
    context.update(get_base_template_context(family, query_period, start_date))
    
    return render(request, 'finances/dashboard.html', context)


# === AJAX Endpoints ===

@login_required
@require_POST
@db_transaction.atomic
def reorder_flow_items_ajax(request):
    """
    Handles AJAX request to reorder Transactions within a FlowGroup.
    Receives array of {id, order} objects and updates the order field.
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")
    
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")
    
    try:
        data = json.loads(request.body)
        items_data = data.get('items', [])
        
        if not items_data:
            return JsonResponse({'error': 'No items data provided.'}, status=400)
        
        # Update each transaction's order
        for item_data in items_data:
            item_id = item_data.get('id')
            new_order = item_data.get('order')
            
            if item_id and new_order is not None:
                transaction = Transaction.objects.filter(
                    id=item_id,
                    flow_group__family=family
                ).first()
                
                if transaction:
                    # Check if user has permission to reorder
                    flow_group = transaction.flow_group
                    if can_access_flow_group(flow_group, current_member):
                        transaction.order = new_order
                        transaction.save(update_fields=['order'])
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        return JsonResponse({'error': f'A server error occurred: {str(e)}'}, status=500)



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
        is_child_manual = data.get('is_child_manual', False)
        is_child_expense = data.get('is_child_expense', False)
        
        # Basic validation
        if not all([flow_group_id, description, amount_str, date_str]):
            return JsonResponse({'error': 'Missing required fields.'}, status=400)
            
        amount = Decimal(amount_str)
        date = dt_datetime.strptime(date_str, '%Y-%m-%d').date()

        flow_group = get_object_or_404(FlowGroup, id=flow_group_id, family=family)
        
        # Check access permissions
        if not can_access_flow_group(flow_group, current_member):
            return HttpResponseForbidden("You don't have permission to edit this group.")

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
        
        # Set is_child_manual_income flag if this is a manual income by a CHILD
        if is_child_manual and current_member.role == 'CHILD' and flow_group.group_type == FLOW_TYPE_INCOME:
            transaction.is_child_manual_income = True

        if is_child_expense and current_member.role == 'CHILD' and flow_group.group_type != FLOW_TYPE_INCOME:
            transaction.is_child_expense = True
        
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

    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")

    try:
        data = json.loads(request.body)
        transaction_id = data.get('transaction_id')

        if not transaction_id:
            return JsonResponse({'error': 'Missing transaction_id.'}, status=400)

        transaction = get_object_or_404(Transaction, id=transaction_id, flow_group__family=family)
        
        # Check access permissions
        if not can_access_flow_group(transaction.flow_group, current_member):
            return HttpResponseForbidden("You don't have permission to delete from this group.")
        
        transaction.delete()

        return JsonResponse({'status': 'success', 'transaction_id': transaction_id})

    except Exception as e:
        return JsonResponse({'error': f'A server error occurred: {str(e)}'}, status=500)


@login_required
@require_POST
@db_transaction.atomic
def toggle_kids_group_realized_ajax(request):
    """
    Handles AJAX request to toggle FlowGroup.realized for Kids groups.
    Only Parents and Admins can toggle this.
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")
    
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")
    
    # Only Parents and Admins can toggle
    if current_member.role not in ['ADMIN', 'PARENT']:
        return HttpResponseForbidden("Only Parents and Admins can mark Kids groups as realized.")
    
    try:
        data = json.loads(request.body)
        flow_group_id = data.get('flow_group_id')
        new_realized_status = data.get('realized', False)
        
        if not flow_group_id:
            return JsonResponse({'error': 'Missing flow_group_id.'}, status=400)
        
        flow_group = get_object_or_404(FlowGroup, id=flow_group_id, family=family)
        
        # Must be a Kids group
        if not flow_group.is_kids_group:
            return JsonResponse({'error': 'Can only toggle realized for Kids groups.'}, status=400)
        
        # Update realized status
        flow_group.realized = new_realized_status
        flow_group.save()
        
        return JsonResponse({
            'status': 'success',
            'flow_group_id': flow_group.id,
            'realized': flow_group.realized,
            'budget': str(flow_group.budgeted_amount)
        })
        
    except Exception as e:
        return JsonResponse({'error': f'A server error occurred: {str(e)}'}, status=500)


@login_required
@require_POST
@db_transaction.atomic
def reorder_flow_groups_ajax(request):
    """
    Handles AJAX request to reorder FlowGroups.
    Receives array of {id, order} objects and updates the order field.
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")
    
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")
    
    try:
        data = json.loads(request.body)
        groups_data = data.get('groups', [])
        
        if not groups_data:
            return JsonResponse({'error': 'No groups data provided.'}, status=400)
        
        # Update each group's order
        for group_data in groups_data:
            group_id = group_data.get('id')
            new_order = group_data.get('order')
            
            if group_id and new_order is not None:
                flow_group = FlowGroup.objects.filter(
                    id=group_id,
                    family=family
                ).first()
                
                if flow_group:
                    # Check if user has permission to reorder
                    # Only accessible groups can be reordered
                    if can_access_flow_group(flow_group, current_member):
                        flow_group.order = new_order
                        flow_group.save(update_fields=['order'])
        
        return JsonResponse({'status': 'success'})
        
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
        
        # Only owner or admin can delete
        if flow_group.owner != request.user and current_member.role != 'ADMIN':
            return JsonResponse({'error': 'Permission denied.'}, status=403)
        
        group_name = flow_group.name
        
        # Delete the group (CASCADE will delete all transactions)
        flow_group.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': f"Flow Group '{group_name}' and all its data have been deleted."
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
@db_transaction.atomic
def copy_previous_period_ajax(request):
    """
    Copies all data from previous period to current period.
    Excludes child-created data.
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")
    
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")
    
    # Only admins and parents can copy period data
    if current_member.role not in ['ADMIN', 'PARENT']:
        return HttpResponseForbidden("Only Admins and Parents can copy period data.")
    
    try:
        # Check if current period already has data
        if current_period_has_data(family):
            return JsonResponse({
                'error': 'Current period already has data. Cannot copy.'
            }, status=400)
        
        # Copy data
        result = copy_previous_period_data(family, exclude_child_data=True)
        
        return JsonResponse({
            'status': 'success',
            'groups_copied': result['groups_copied'],
            'transactions_copied': result['transactions_copied'],
            'message': f"Copied {result['groups_copied']} groups and {result['transactions_copied']} transactions from previous period."
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error copying period: {str(e)}'}, status=500)


@login_required
def check_period_empty_ajax(request):
    """
    Checks if current period is empty (for showing copy button).
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")
    
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")
    
    try:
        has_data = current_period_has_data(family)
        
        return JsonResponse({
            'status': 'success',
            'has_data': has_data,
            'can_copy': not has_data and current_member.role in ['ADMIN', 'PARENT']
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error checking period: {str(e)}'}, status=500)




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
    import datetime
    from .utils import apply_period_configuration_change
    
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return redirect('dashboard')
    
    query_period = request.GET.get('period')
    start_date, end_date, _ = get_current_period_dates(family, query_period)
    
    config, _ = FamilyConfiguration.objects.get_or_create(family=family)
    
    if request.method == 'POST':
        form = FamilyConfigurationForm(request.POST, instance=config)
        if form.is_valid():
            # Get new values from form
            new_period_type = form.cleaned_data.get('period_type')
            new_starting_day = form.cleaned_data.get('starting_day')
            new_base_date = form.cleaned_data.get('base_date')
            
            # Store OLD values before any changes
            old_period_type = config.period_type
            old_starting_day = config.starting_day
            old_base_date = config.base_date
            
            # Check impact of changes
            impact = check_period_change_impact(
                family, 
                new_period_type, 
                new_starting_day, 
                new_base_date
            )
            
            # If significant change detected and user hasn't confirmed yet
            if impact['requires_close'] and not request.POST.get('confirmed'):
                # Show confirmation in context
                context = {
                    'form': form,
                    'show_confirmation': True,
                    'impact': impact,
                    'pending_changes': {
                        'period_type': new_period_type,
                        'starting_day': new_starting_day,
                        'base_date': new_base_date.isoformat() if new_base_date else None,
                    }
                }
                context.update(get_base_template_context(family, query_period, start_date))
                return render(request, 'finances/configurations.html', context)
            
            # User confirmed or no significant change
            if impact['requires_close']:
                # Get period boundaries
                current_start, current_end, _ = impact['current_period']
                new_start, new_end, _ = impact['new_current_period']
                adjustment_period = impact.get('adjustment_period')
                
                # Prepare old and new config dictionaries for apply function
                old_config = {
                    'period_type': old_period_type,
                    'starting_day': old_starting_day,
                    'base_date': old_base_date,
                    'current_start': current_start,
                    'current_end': current_end
                }
                
                new_config = {
                    'period_type': new_period_type,
                    'starting_day': new_starting_day,
                    'base_date': new_base_date,
                    'new_start': new_start,
                    'new_end': new_end
                }
                
                # Apply the configuration change (creates closed periods, copies flow groups)
                results = apply_period_configuration_change(
                    family,
                    old_config,
                    new_config,
                    adjustment_period
                )
                
                # NOW save the new configuration
                form.save()
                
                # Create success message
                if adjustment_period:
                    adj_start, adj_end = adjustment_period
                    adj_days = (adj_end - adj_start).days + 1
                    msg = (f'Configuration updated successfully. Created adjustment period of {adj_days} days '
                          f'({adj_start.strftime("%b %d")} to {adj_end.strftime("%b %d")}). '
                          f'New period starts: {new_start.strftime("%b %d, %Y")}. '
                          f'Copied {results["flow_groups_copied"]} Flow Groups.')
                    
                    if results['future_transactions_adjusted'] > 0:
                        msg += f' Adjusted {results["future_transactions_adjusted"]} future transaction(s) to {new_start.strftime("%b %d")}.'
                    
                    messages.success(request, msg)
                else:
                    msg = (f'Configuration updated successfully. '
                          f'Period adjusted to start on {new_start.strftime("%b %d, %Y")}. '
                          f'Copied {results["flow_groups_copied"]} Flow Groups.')
                    
                    if results['future_transactions_adjusted'] > 0:
                        msg += f' Adjusted {results["future_transactions_adjusted"]} future transaction(s) to {new_start.strftime("%b %d")}.'
                    
                    messages.success(request, msg)
            else:
                # No need to close, just save
                form.save()
                messages.success(request, 'Configuration updated successfully.')
            
            redirect_url = f"?period={query_period}" if query_period else ""
            return redirect(f"/settings/{redirect_url}")
    else:
        form = FamilyConfigurationForm(instance=config)
    
    context = {
        'form': form,
        'show_confirmation': False,
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
        form = FlowGroupForm(request.POST, family=family)
        if form.is_valid():
            flow_group = form.save(commit=False)
            flow_group.family = family
            flow_group.owner = request.user
            flow_group.group_type = EXPENSE_MAIN
            # CRITICAL: Use the period from query/POST parameter, not current date
            flow_group.period_start_date = start_date
            
            # Validation for CHILD users: budget cannot exceed manual income
            if current_member.role == 'CHILD':
                # Calculate child's manual income total for this period
                child_manual_income_total = Transaction.objects.filter(
                    flow_group__group_type=FLOW_TYPE_INCOME,
                    flow_group__family=family,
                    date__range=(start_date, end_date),
                    member=current_member,
                    is_child_manual_income=True
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                
                if flow_group.budgeted_amount > child_manual_income_total:
                    messages.error(request, f"Budget cannot exceed your available balance (${child_manual_income_total}). Please enter a budget of ${child_manual_income_total} or less.")
                    context = {
                        'form': form,
                        'start_date': start_date,
                        'end_date': end_date,
                        'current_member': current_member,
                        'child_max_budget': child_manual_income_total,
                    }
                    context.update(get_base_template_context(family, query_period, start_date))
                    return render(request, 'finances/add_flow_group.html', context)
                
                # CHILD FlowGroups are automatically shared with all Parents/Admins
                flow_group.is_shared = True
            
            # If Kids group is checked, automatically enable shared
            if flow_group.is_kids_group:
                flow_group.is_shared = True
            
            flow_group.save()
            
            # If CHILD created the group, auto-assign all Parents/Admins
            if current_member.role == 'CHILD':
                parents_admins = FamilyMember.objects.filter(
                    family=family,
                    role__in=['ADMIN', 'PARENT']
                )
                flow_group.assigned_members.set(parents_admins)
            else:
                # Save assigned members/children (ManyToMany field)
                form.save_m2m()
            
            messages.success(request, f"Flow Group '{flow_group.name}' created for period starting {start_date.strftime('%B %d, %Y')}.")
            # Preserve period in redirect
            redirect_url = f"?period={start_date.strftime('%Y-%m-%d')}"
            return redirect(f"/flow-group/{flow_group.id}/edit/{redirect_url}")
    else:
        form = FlowGroupForm(family=family)

    # Get default date for this period
    default_date = get_default_date_for_period(start_date, end_date)
    
    # Calculate max budget for child users
    child_max_budget = None
    if current_member.role == 'CHILD':
        child_max_budget = Transaction.objects.filter(
            flow_group__group_type=FLOW_TYPE_INCOME,
            flow_group__family=family,
            date__range=(start_date, end_date),
            member=current_member,
            is_child_manual_income=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

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
    family, current_member, family_members = get_family_context(request.user)
    if not family:
        return redirect('dashboard')
        
    group = get_object_or_404(FlowGroup, id=group_id, family=family)
    
    # Check access permissions
    if not can_access_flow_group(group, current_member):
        messages.error(request, "You don't have permission to access this group.")
        return redirect('dashboard')
    
    # Get period from query parameter, or use the group's period
    query_period = request.GET.get('period')
    if not query_period:
        # Use the FlowGroup's period_start_date as the default
        query_period = group.period_start_date.strftime('%Y-%m-%d')
    
    start_date, end_date, _ = get_current_period_dates(family, query_period)
    
    from .utils import get_member_role_for_period
    member_role_for_period = get_member_role_for_period(current_member, start_date)
    
    
    # Check if user can edit (owner or admin/parent for shared/kids groups)
    can_edit_group = (
        group.owner == request.user or 
        current_member.role in ['ADMIN', 'PARENT']
    )
    
    # Children can only edit budget if it's a kids group and they're assigned
    can_edit_budget = can_edit_group
    if current_member.role == 'CHILD':
        can_edit_budget = False
    
    if request.method == 'POST' and can_edit_group:
        form = FlowGroupForm(request.POST, instance=group, family=family)
        if form.is_valid():
            flow_group = form.save(commit=False)
            
            # If Kids group is checked, automatically enable shared
            if flow_group.is_kids_group:
                flow_group.is_shared = True
            
            flow_group.save()
            
            # Save assigned children (ManyToMany field)
            form.save_m2m()
            
            messages.success(request, f"Flow Group '{group.name}' updated.")
            # Preserve period in redirect
            redirect_url = f"?period={query_period}" if query_period else ""
            return redirect(f"/flow-group/{group_id}/edit/{redirect_url}")
    else:
        form = FlowGroupForm(instance=group, family=family)

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
        'can_edit_group': can_edit_group,
        'can_edit_budget': can_edit_budget,
        'member_role_for_period' : member_role_for_period,
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
@db_transaction.atomic
def copy_previous_period_ajax(request):
    """
    Copies all data from previous period to current period.
    Excludes child-created data.
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")
    
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")
    
    # Only admins and parents can copy period data
    if current_member.role not in ['ADMIN', 'PARENT']:
        return HttpResponseForbidden("Only Admins and Parents can copy period data.")
    
    try:
        # Check if current period already has data
        if current_period_has_data(family):
            return JsonResponse({
                'error': 'Current period already has data. Cannot copy.'
            }, status=400)
        
        # Copy data
        result = copy_previous_period_data(family, exclude_child_data=True)
        
        return JsonResponse({
            'status': 'success',
            'groups_copied': result['groups_copied'],
            'transactions_copied': result['transactions_copied'],
            'message': f"Copied {result['groups_copied']} groups and {result['transactions_copied']} transactions from previous period."
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error copying period: {str(e)}'}, status=500)


@login_required
def check_period_empty_ajax(request):
    """
    Checks if current period is empty (for showing copy button).
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")
    
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")
    
    try:
        has_data = current_period_has_data(family)
        
        return JsonResponse({
            'status': 'success',
            'has_data': has_data,
            'can_copy': not has_data and current_member.role in ['ADMIN', 'PARENT']
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error checking period: {str(e)}'}, status=500)




@login_required
@require_POST 
def investment_add_view(request):
    query_period = request.GET.get('period')
    redirect_url = f"?period={query_period}" if query_period else ""
    return redirect(f"/investments/{redirect_url}")
