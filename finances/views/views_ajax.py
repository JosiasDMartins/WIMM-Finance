import json
import decimal
from decimal import Decimal
from datetime import datetime as dt_datetime

from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db import transaction as db_transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404
from moneyed import Money
from ..notification_utils import create_new_transaction_notification

# Importações relativas do app (.. sobe um nível, de /views/ para /finances/)
from ..models import Transaction, FlowGroup, FamilyMember, BankBalance, FLOW_TYPE_INCOME
from ..utils import (
    current_period_has_data, 
    copy_previous_period_data,
    get_current_period_dates,
    ensure_period_exists,
    get_period_currency,
    get_available_periods
)

# Importações de utils locais (mesmo pacote /views/)
from .views_utils import (
    get_family_context,
    can_access_flow_group,
    get_currency_symbol,
    get_thousand_separator
)


@login_required
@require_POST
@db_transaction.atomic
def reorder_flow_items_ajax(request):
    """AJAX: Reorders transactions (items) within a FlowGroup."""
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
        
        for item_data in items_data:
            item_id = item_data.get('id')
            new_order = item_data.get('order')
            
            if item_id and new_order is not None:
                transaction = Transaction.objects.filter(
                    id=item_id,
                    flow_group__family=family
                ).first()
                
                if transaction:
                    if can_access_flow_group(transaction.flow_group, current_member):
                        transaction.order = new_order
                        transaction.save(update_fields=['order'])
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        return JsonResponse({'error': f'A server error occurred: {str(e)}'}, status=500)


@login_required
@require_POST
@db_transaction.atomic
def save_flow_item_ajax(request):
    """AJAX: Saves or updates a transaction (item)."""
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
        
        print(f"[DEBUG] save_flow_item_ajax called - transaction_id: {transaction_id}, type: {type(transaction_id)}")
        
        if not all([flow_group_id, description, amount_str, date_str]):
            return JsonResponse({'error': 'Missing required fields.'}, status=400)
        
        flow_group = get_object_or_404(FlowGroup, id=flow_group_id, family=family)
        currency = get_period_currency(family, flow_group.period_start_date)
        
        try:
            amount_clean = str(amount_str).strip()
            amount_clean = amount_clean.replace(get_currency_symbol(currency), '')
            amount_clean = amount_clean.replace(get_thousand_separator(), '')
            
            if not amount_clean:
                return JsonResponse({'error': 'Amount cannot be empty.'}, status=400)
            amount = Decimal(amount_clean)
        except (ValueError, decimal.InvalidOperation) as e:
            return JsonResponse({'error': f'Invalid amount format: {amount_str}'}, status=400)
            
        date = dt_datetime.strptime(date_str, '%Y-%m-%d').date()
        
        if not can_access_flow_group(flow_group, current_member):
            return HttpResponseForbidden("You don't have permission to edit this group.")

        # Determinar se é nova transação ou edição
        is_new = False
        if not transaction_id or transaction_id == '0' or transaction_id == 'NEW' or transaction_id is None:
            is_new = True
            print(f"[DEBUG] New transaction detected")
        else:
            print(f"[DEBUG] Updating existing transaction: {transaction_id}")
            
        if is_new:
            # Nova transação
            max_order = Transaction.objects.filter(flow_group=flow_group).aggregate(max_order=Max('order'))['max_order']
            new_order = (max_order or 0) + 1
            transaction = Transaction(flow_group=flow_group, order=new_order)
            
            if member_id:
                member = get_object_or_404(FamilyMember, id=member_id, family=family)
            else:
                member = current_member
            transaction.member = member
        else:
            # Atualização de transação existente
            transaction = get_object_or_404(Transaction, id=transaction_id, flow_group=flow_group)
            if member_id:
                member = get_object_or_404(FamilyMember, id=member_id, family=family)
                transaction.member = member

        transaction.description = description
        transaction.amount = Money(abs(amount), currency)
        transaction.date = date
        transaction.realized = realized
        
        if is_child_manual and current_member.role == 'CHILD' and flow_group.group_type == FLOW_TYPE_INCOME:
            transaction.is_child_manual_income = True

        if is_child_expense and current_member.role == 'CHILD' and flow_group.group_type != FLOW_TYPE_INCOME:
            transaction.is_child_expense = True
        
        transaction.save()
        print(f"[DEBUG] Transaction saved with ID: {transaction.id}")

        # Criar notificação SEMPRE (para novas transações e edições)
        print(f"[DEBUG] Attempting to create notification for transaction {transaction.id}")
        print(f"[DEBUG] Current member: {current_member.user.username} (ID: {current_member.id})")
        print(f"[DEBUG] FlowGroup: {flow_group.name} (ID: {flow_group.id})")
        
        try:
            notif_count = create_new_transaction_notification(
                transaction=transaction,
                exclude_member=current_member
            )
            print(f"[DEBUG] Notifications created: {notif_count}")
        except Exception as e:
            # Log error but don't fail the transaction
            print(f"[ERROR] Error creating notification: {e}")
            import traceback
            traceback.print_exc()
        
        config = getattr(family, 'configuration', None)
        if config:
            start_date, end_date, _ = get_current_period_dates(family, flow_group.period_start_date.strftime('%Y-%m-%d'))
            ensure_period_exists(family, start_date, end_date, config.period_type)

        amount_value = str(transaction.amount.amount)
        currency_code = transaction.amount.currency.code
        currency_symbol = get_currency_symbol(currency_code)

        return JsonResponse({
            'status': 'success',
            'transaction_id': transaction.id,
            'description': transaction.description,
            'amount': amount_value,
            'currency': currency_code,
            'currency_symbol': currency_symbol,
            'date': transaction.date.strftime('%Y-%m-%d'),
            'member_id': transaction.member.id,
            'member_name': transaction.member.user.username,
            'realized': transaction.realized,
        })

    except ValueError as e:
        return JsonResponse({'error': f'Invalid data format: {str(e)}'}, status=400)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[ERROR] Error in save_flow_item_ajax: {error_trace}")
        return JsonResponse({'error': f'A server error occurred: {str(e)}'}, status=500)


@login_required
@require_POST
@db_transaction.atomic
def delete_flow_item_ajax(request):
    """AJAX: Deletes a transaction (item)."""
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
    """AJAX: Toggles the 'realized' status of a Kids group (allowance)."""
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")
    
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")
    
    if current_member.role not in ['ADMIN', 'PARENT']:
        return HttpResponseForbidden("Only Parents and Admins can mark Kids groups as realized.")
    
    try:
        data = json.loads(request.body)
        flow_group_id = data.get('flow_group_id')
        new_realized_status = data.get('realized', False)
        
        if not flow_group_id:
            return JsonResponse({'error': 'Missing flow_group_id.'}, status=400)
        
        flow_group = get_object_or_404(FlowGroup, id=flow_group_id, family=family)
        
        if not flow_group.is_kids_group:
            return JsonResponse({'error': 'Can only toggle realized for Kids groups.'}, status=400)
        
        flow_group.realized = new_realized_status
        flow_group.save()
        
        budget_value = str(flow_group.budgeted_amount.amount)
        
        return JsonResponse({
            'status': 'success',
            'flow_group_id': flow_group.id,
            'realized': flow_group.realized,
            'budget': budget_value
        })
        
    except Exception as e:
        return JsonResponse({'error': f'A server error occurred: {str(e)}'}, status=500)


@login_required
@require_POST
@db_transaction.atomic
def reorder_flow_groups_ajax(request):
    """AJAX: Reorders FlowGroups on the dashboard."""
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
        
        for group_data in groups_data:
            group_id = group_data.get('id')
            new_order = group_data.get('order')
            
            if group_id and new_order is not None:
                flow_group = FlowGroup.objects.filter(id=group_id, family=family).first()
                
                if flow_group:
                    if can_access_flow_group(flow_group, current_member):
                        flow_group.order = new_order
                        flow_group.save(update_fields=['order'])
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        return JsonResponse({'error': f'A server error occurred: {str(e)}'}, status=500)


@login_required
@require_POST
@db_transaction.atomic
def delete_flow_group_view(request, group_id):
    """AJAX: Deletes a FlowGroup and all its transactions."""
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return JsonResponse({'error': 'User is not associated with a family.'}, status=403)
    
    try:
        flow_group = get_object_or_404(FlowGroup, id=group_id, family=family)
        
        if flow_group.owner != request.user and current_member.role != 'ADMIN':
            return JsonResponse({'error': 'Permission denied.'}, status=403)
        
        group_name = flow_group.name
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
    """AJAX: Copies data from the previous period to the current one."""
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest("Not an AJAX request.")
    
    family, current_member, _ = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")
    
    if current_member.role not in ['ADMIN', 'PARENT']:
        return HttpResponseForbidden("Only Admins and Parents can copy period data.")
    
    try:
        if current_period_has_data(family):
            return JsonResponse({'error': 'Current period already has data. Cannot copy.'}, status=400)
        
        result = copy_previous_period_data(family, exclude_child_data=True)
        
        return JsonResponse({
            'status': 'success',
            'groups_copied': result['groups_copied'],
            'transactions_copied': result['transactions_copied'],
            'message': f"Copied {result['groups_copied']} groups and {result['transactions_copied']} transactions."
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error copying period: {str(e)}'}, status=500)


@login_required
def check_period_empty_ajax(request):
    """AJAX: Checks if the current period is empty (to show the copy button)."""
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
def get_periods_ajax(request):
    """AJAX: Returns the available time periods in JSON format."""
    family, _, _ = get_family_context(request.user)
    if not family:
        return JsonResponse({'error': 'User is not associated with a family.'}, status=403)
    
    periods = get_available_periods(family)
    
    periods_data = [{
        'label': p['label'],
        'value': p['value'],
        'is_current': p['is_current'],
        'has_data': p['has_data']
    } for p in periods]
    
    return JsonResponse({'periods': periods_data})


@login_required
@require_POST
def save_bank_balance_ajax(request):
    """AJAX: Saves a bank balance entry."""
    try:
        data = json.loads(request.body)
        
        family, _, _ = get_family_context(request.user)
        if not family:
            return JsonResponse({'status': 'error', 'error': 'User not in family'}, status=403)
        
        description = data.get('description', '').strip()
        amount = Decimal(data.get('amount', '0'))
        date_str = data.get('date')
        member_id = data.get('member_id')
        period_start_date_str = data.get('period_start_date')
        balance_id = data.get('id')
        
        date = dt_datetime.strptime(date_str, '%Y-%m-%d').date()
        period_start_date = dt_datetime.strptime(period_start_date_str, '%Y-%m-%d').date()
        
        member = None
        if member_id and member_id != 'null':
            member = FamilyMember.objects.get(id=member_id, family=family)
        
        currency = get_period_currency(family, period_start_date)
        money_amount = Money(amount, currency)
        
        if balance_id and balance_id != 'new':
            bank_balance = BankBalance.objects.get(id=balance_id, family=family)
            bank_balance.description = description
            bank_balance.amount = money_amount
            bank_balance.date = date
            bank_balance.member = member
            bank_balance.save()
        else:
            bank_balance = BankBalance.objects.create(
                family=family,
                member=member,
                description=description,
                amount=money_amount,
                date=date,
                period_start_date=period_start_date
            )
        
        amount_value = str(bank_balance.amount.amount)
        
        return JsonResponse({
            'status': 'success',
            'id': bank_balance.id,
            'description': bank_balance.description,
            'amount': amount_value,
            'date': bank_balance.date.strftime('%Y-%m-%d'),
            'member_id': bank_balance.member.id if bank_balance.member else None,
            'member_name': bank_balance.member.user.username if bank_balance.member else 'Family',
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=400)


@login_required
@require_POST
def delete_bank_balance_ajax(request):
    """AJAX: Deletes a bank balance entry."""
    try:
        data = json.loads(request.body)
        balance_id = data.get('id')
        
        family, _, _ = get_family_context(request.user)
        if not family:
            return JsonResponse({'status': 'error', 'error': 'User not in family'}, status=403)
        
        bank_balance = BankBalance.objects.get(id=balance_id, family=family)
        bank_balance.delete()
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=400)