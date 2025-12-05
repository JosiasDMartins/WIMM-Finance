import json
import decimal
from decimal import Decimal
from datetime import datetime as dt_datetime

from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.db import transaction as db_transaction
from django.db.models import Max, Q, Sum
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
    get_thousand_separator,
    get_decimal_separator
)


@login_required
@require_POST
@db_transaction.atomic
def reorder_flow_items_ajax(request):
    """AJAX: Reorders transactions (items) within a FlowGroup."""
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest(_("Not an AJAX request."))

    family, current_member, _unused = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden(_("User is not associated with a family."))
    
    try:
        data = json.loads(request.body)
        items_data = data.get('items', [])
        
        if not items_data:
            return JsonResponse({'error': _('No items data provided.')}, status=400)
        
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
        return JsonResponse({'error': _('A server error occurred: %(error)s') % {'error': str(e)}}, status=500)


@login_required
@require_POST
@db_transaction.atomic
def save_flow_item_ajax(request):
    """AJAX: Saves or updates a transaction (item)."""
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest(_("Not an AJAX request."))

    family, current_member, _unused = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden(_("User is not associated with a family."))

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
        is_fixed = data.get('is_fixed', False)
        
        print(f"[DEBUG] save_flow_item_ajax called - transaction_id: {transaction_id}, type: {type(transaction_id)}")
        
        if not all([flow_group_id, description, amount_str, date_str]):
            return JsonResponse({'error': _('Missing required fields.')}, status=400)
        
        flow_group = get_object_or_404(FlowGroup, id=flow_group_id, family=family)
        currency = get_period_currency(family, flow_group.period_start_date)
        
        try:
            amount_clean = str(amount_str).strip()
            print(f"[DEBUG] Step 1 - Raw input: '{amount_str}'")

            # IMPORTANT: Frontend getRawValue() already sends values in standard format "1234.56"
            # We should NOT do locale-based cleaning because:
            # 1. Frontend already removes thousand separators
            # 2. Frontend already converts decimal separator to dot
            # 3. Doing locale cleaning here causes bugs (e.g., "12.34" becomes "1234" in PT_BR)

            # Only remove currency symbol if present (edge case)
            curr_symbol = get_currency_symbol(currency)
            if curr_symbol in amount_clean:
                amount_clean = amount_clean.replace(curr_symbol, '')
                print(f"[DEBUG] Step 2 - After removing currency symbol '{curr_symbol}': '{amount_clean}'")

            # DO NOT remove thousand separators or replace decimal separators!
            # Frontend already sends in standard format "1234.56"

            if not amount_clean:
                return JsonResponse({'error': _('Amount cannot be empty.')}, status=400)
            amount = Decimal(amount_clean)
            print(f"[DEBUG] Step 3 - Final Decimal value: {amount}")
        except (ValueError, decimal.InvalidOperation) as e:
            return JsonResponse({'error': _('Invalid amount format: %(amount)s') % {'amount': amount_str}}, status=400)
            
        date = dt_datetime.strptime(date_str, '%Y-%m-%d').date()
        
        if not can_access_flow_group(flow_group, current_member):
            return HttpResponseForbidden(_("You don't have permission to edit this group."))

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
        money_obj = Money(abs(amount), currency)
        print(f"[DEBUG] Creating Money object - Decimal: {abs(amount)}, Currency: {currency}, Money.amount: {money_obj.amount}")
        transaction.amount = money_obj
        transaction.date = date
        transaction.realized = realized
        transaction.is_fixed = is_fixed

        if is_child_manual and current_member.role == 'CHILD' and flow_group.group_type == FLOW_TYPE_INCOME:
            transaction.is_child_manual_income = True

        if is_child_expense and current_member.role == 'CHILD' and flow_group.group_type != FLOW_TYPE_INCOME:
            transaction.is_child_expense = True
        
        transaction.save()
        print(f"[DEBUG] Transaction saved with ID: {transaction.id}")
        print(f"[DEBUG] After save - transaction.amount.amount: {transaction.amount.amount}")

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
            start_date, end_date, _unused = get_current_period_dates(family, flow_group.period_start_date.strftime('%Y-%m-%d'))
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
            'is_fixed': transaction.is_fixed,
        })

    except ValueError as e:
        return JsonResponse({'error': _('Invalid data format: %(error)s') % {'error': str(e)}}, status=400)
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

    family, current_member, _unused = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden("User is not associated with a family.")

    try:
        data = json.loads(request.body)
        transaction_id = data.get('transaction_id')

        if not transaction_id:
            return JsonResponse({'error': _('Missing transaction_id.')}, status=400)

        transaction = get_object_or_404(Transaction, id=transaction_id, flow_group__family=family)
        
        if not can_access_flow_group(transaction.flow_group, current_member):
            return HttpResponseForbidden(_("You don't have permission to delete from this group."))
        
        transaction.delete()

        return JsonResponse({'status': 'success', 'transaction_id': transaction_id})

    except Exception as e:
        return JsonResponse({'error': _('A server error occurred: %(error)s') % {'error': str(e)}}, status=500)


@login_required
@require_POST
@db_transaction.atomic
def toggle_kids_group_realized_ajax(request):
    """AJAX: Toggles the 'realized' status of a Kids group (allowance)."""
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest(_("Not an AJAX request."))

    family, current_member, _unused = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden(_("User is not associated with a family."))

    if current_member.role not in ['ADMIN', 'PARENT']:
        return HttpResponseForbidden(_("Only Parents and Admins can mark Kids groups as realized."))

    try:
        data = json.loads(request.body)
        flow_group_id = data.get('flow_group_id')
        new_realized_status = data.get('realized', False)

        if not flow_group_id:
            return JsonResponse({'error': _('Missing flow_group_id.')}, status=400)

        flow_group = get_object_or_404(FlowGroup, id=flow_group_id, family=family)

        if not flow_group.is_kids_group:
            return JsonResponse({'error': _('Can only toggle realized for Kids groups.')}, status=400)

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
        return JsonResponse({'error': _('A server error occurred: %(error)s') % {'error': str(e)}}, status=500)


@login_required
@require_POST
@db_transaction.atomic
def toggle_credit_card_closed_ajax(request):
    """AJAX: Toggles the 'closed' status of a Credit Card group."""
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest(_("Not an AJAX request."))

    family, current_member, _unused = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden(_("User is not associated with a family."))

    if current_member.role not in ['ADMIN', 'PARENT']:
        return HttpResponseForbidden(_("Only Parents and Admins can mark Credit Card groups as closed."))

    try:
        data = json.loads(request.body)
        flow_group_id = data.get('flow_group_id')
        new_closed_status = data.get('closed', False)

        if not flow_group_id:
            return JsonResponse({'error': _('Missing flow_group_id.')}, status=400)

        flow_group = get_object_or_404(FlowGroup, id=flow_group_id, family=family)

        if not flow_group.is_credit_card:
            return JsonResponse({'error': _('Can only toggle closed for Credit Card groups.')}, status=400)

        flow_group.closed = new_closed_status
        flow_group.save()

        # When closing the bill (closed=True), mark all transactions as realized
        if new_closed_status:
            transactions_updated = Transaction.objects.filter(
                flow_group=flow_group
            ).update(realized=True)
        else:
            transactions_updated = 0

        budget_value = str(flow_group.budgeted_amount.amount)

        return JsonResponse({
            'status': 'success',
            'flow_group_id': flow_group.id,
            'closed': flow_group.closed,
            'budget': budget_value,
            'transactions_updated': transactions_updated
        })

    except Exception as e:
        return JsonResponse({'error': _('A server error occurred: %(error)s') % {'error': str(e)}}, status=500)


@login_required
@require_POST
@db_transaction.atomic
def reorder_flow_groups_ajax(request):
    """AJAX: Reorders FlowGroups on the dashboard."""
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest(_("Not an AJAX request."))

    family, current_member, _unused = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden(_("User is not associated with a family."))
    
    try:
        data = json.loads(request.body)
        groups_data = data.get('groups', [])
        
        if not groups_data:
            return JsonResponse({'error': _('No groups data provided.')}, status=400)
        
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
        return JsonResponse({'error': _('A server error occurred: %(error)s') % {'error': str(e)}}, status=500)


@login_required
@require_POST
def reorder_income_items_ajax(request):
    """AJAX: Reorders Income items on the dashboard."""
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest(_("Not an AJAX request."))

    family, current_member, _unused = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden(_("User is not associated with a family."))

    try:
        data = json.loads(request.body)
        items_data = data.get('items', [])

        if not items_data:
            return JsonResponse({'error': _('No items data provided.')}, status=400)

        for item_data in items_data:
            item_id = item_data.get('id')
            new_order = item_data.get('order')

            if item_id and new_order is not None:
                income_item = Transaction.objects.filter(
                    id=item_id,
                    flow_group__family=family,
                    flow_group__group_type='INCOME'
                ).first()

                if income_item:
                    # Check permissions - income items don't have owner, check via member
                    if income_item.member and (income_item.member.user == request.user or current_member.role == 'ADMIN'):
                        income_item.order = new_order
                        income_item.save(update_fields=['order'])
                    elif current_member.role == 'ADMIN':
                        # Allow admin to reorder any income
                        income_item.order = new_order
                        income_item.save(update_fields=['order'])

        return JsonResponse({'status': 'success'})

    except Exception as e:
        return JsonResponse({'error': _('A server error occurred: %(error)s') % {'error': str(e)}}, status=500)


@login_required
@require_POST
@db_transaction.atomic
def delete_flow_group_view(request, group_id):
    """AJAX: Deletes a FlowGroup and all its transactions."""
    family, current_member, _unused = get_family_context(request.user)
    if not family:
        return JsonResponse({'error': _('User is not associated with a family.')}, status=403)
    
    try:
        flow_group = get_object_or_404(FlowGroup, id=group_id, family=family)
        
        if flow_group.owner != request.user and current_member.role != 'ADMIN':
            return JsonResponse({'error': _('Permission denied.')}, status=403)
        
        group_name = flow_group.name
        flow_group.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': _("Flow Group '%(name)s' and all its data have been deleted.") % {'name': group_name}
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
@db_transaction.atomic
def copy_previous_period_ajax(request):
    """AJAX: Copies data from the previous period to the current one."""
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest(_("Not an AJAX request."))

    family, current_member, _unused = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden(_("User is not associated with a family."))
    
    if current_member.role not in ['ADMIN', 'PARENT']:
        return HttpResponseForbidden(_("Only Admins and Parents can copy period data."))
    
    try:
        if current_period_has_data(family):
            return JsonResponse({'error': _('Current period already has data. Cannot copy.')}, status=400)
        
        result = copy_previous_period_data(family, exclude_child_data=True)
        
        return JsonResponse({
            'status': 'success',
            'groups_copied': result['groups_copied'],
            'transactions_copied': result['transactions_copied'],
            'message': _("Copied %(groups)s groups and %(transactions)s transactions.") % {
                'groups': result['groups_copied'],
                'transactions': result['transactions_copied']
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': _('Error copying period: %(error)s') % {'error': str(e)}}, status=500)


@login_required
def check_period_empty_ajax(request):
    """AJAX: Checks if the current period is empty (to show the copy button)."""
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest(_("Not an AJAX request."))

    family, current_member, _unused = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden(_("User is not associated with a family."))
    
    try:
        has_data = current_period_has_data(family)
        
        return JsonResponse({
            'status': 'success',
            'has_data': has_data,
            'can_copy': not has_data and current_member.role in ['ADMIN', 'PARENT']
        })
        
    except Exception as e:
        return JsonResponse({'error': _('Error checking period: %(error)s') % {'error': str(e)}}, status=500)


@login_required
def get_periods_ajax(request):
    """AJAX: Returns the available time periods in JSON format."""
    family, _unused1, _unused2 = get_family_context(request.user)
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
        
        family, _unused1, _unused2 = get_family_context(request.user)
        if not family:
            return JsonResponse({'status': 'error', 'error': _('User not in family')}, status=403)
        
        description = data.get('description', '').strip()
        amount_str = data.get('amount', '0')
        date_str = data.get('date')
        member_id = data.get('member_id')
        period_start_date_str = data.get('period_start_date')
        balance_id = data.get('id')

        # Parse amount - frontend getRawValue() already sends in standard format "1234.56"
        # DO NOT do locale-based cleaning - it causes the 100x multiplication bug
        amount_clean = str(amount_str).strip()

        # Only remove currency symbol if present (edge case)
        curr_symbol = get_currency_symbol(get_period_currency(family, dt_datetime.strptime(period_start_date_str, '%Y-%m-%d').date()))
        if curr_symbol in amount_clean:
            amount_clean = amount_clean.replace(curr_symbol, '')

        amount = Decimal(amount_clean)

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

        family, _unused1, _unused2 = get_family_context(request.user)
        if not family:
            return JsonResponse({'status': 'error', 'error': _('User not in family')}, status=403)

        bank_balance = BankBalance.objects.get(id=balance_id, family=family)
        bank_balance.delete()

        return JsonResponse({'status': 'success'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=400)


@login_required
@require_POST
def validate_period_overlap_ajax(request):
    """AJAX: Validates if a new period would overlap with existing periods."""
    try:
        data = json.loads(request.body)
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')

        family, current_member, _unused = get_family_context(request.user)
        if not family:
            return JsonResponse({'status': 'error', 'error': _('User not in family')}, status=403)

        # Only ADMIN and PARENT can create periods
        if current_member.role not in ['ADMIN', 'PARENT']:
            return JsonResponse({'status': 'error', 'error': _('Permission denied')}, status=403)

        # Parse dates
        start_date = dt_datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = dt_datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Validate: end_date must be after start_date
        if end_date <= start_date:
            return JsonResponse({
                'status': 'error',
                'error': _('End date must be after start date'),
                'has_overlap': False
            })

        # Check for overlapping periods
        from ..models import Period
        overlapping_periods = Period.objects.filter(
            family=family
        ).filter(
            Q(start_date__lte=end_date, end_date__gte=start_date)
        )

        if overlapping_periods.exists():
            overlap_details = []
            for period in overlapping_periods:
                overlap_details.append({
                    'start': period.start_date.strftime('%Y-%m-%d'),
                    'end': period.end_date.strftime('%Y-%m-%d'),
                    'label': f"{period.start_date.strftime('%b %d')} - {period.end_date.strftime('%b %d, %Y')}"
                })

            return JsonResponse({
                'status': 'warning',
                'has_overlap': True,
                'message': _('This period overlaps with existing periods'),
                'overlapping_periods': overlap_details
            })

        return JsonResponse({
            'status': 'success',
            'has_overlap': False,
            'message': _('No overlap detected')
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=400)


@login_required
@require_POST
@db_transaction.atomic
def create_period_ajax(request):
    """AJAX: Creates a new period."""
    try:
        data = json.loads(request.body)
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')

        family, current_member, _unused = get_family_context(request.user)
        if not family:
            return JsonResponse({'status': 'error', 'error': _('User not in family')}, status=403)

        # Only ADMIN and PARENT can create periods
        if current_member.role not in ['ADMIN', 'PARENT']:
            return JsonResponse({'status': 'error', 'error': _('Permission denied')}, status=403)

        # Parse dates
        start_date = dt_datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = dt_datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Validate: end_date must be after start_date
        if end_date <= start_date:
            return JsonResponse({
                'status': 'error',
                'error': _('End date must be after start date')
            }, status=400)

        # Check for overlapping periods (double-check)
        from ..models import Period
        overlapping_periods = Period.objects.filter(
            family=family
        ).filter(
            Q(start_date__lte=end_date, end_date__gte=start_date)
        )

        if overlapping_periods.exists():
            return JsonResponse({
                'status': 'error',
                'error': _('This period overlaps with existing periods')
            }, status=400)

        # Get family configuration
        config = getattr(family, 'configuration', None)
        if not config:
            return JsonResponse({
                'status': 'error',
                'error': _('Family configuration not found')
            }, status=400)

        # Create the new period
        period = Period.objects.create(
            family=family,
            start_date=start_date,
            end_date=end_date,
            period_type=config.period_type,
            currency=config.base_currency
        )

        # Replicate recurring FlowGroups and fixed transactions
        from ..recurring_utils import replicate_recurring_flowgroups
        replication_result = replicate_recurring_flowgroups(family, start_date)

        return JsonResponse({
            'status': 'success',
            'message': _('Period created successfully'),
            'period': {
                'id': period.id,
                'start_date': period.start_date.strftime('%Y-%m-%d'),
                'end_date': period.end_date.strftime('%Y-%m-%d'),
                'label': f"{period.start_date.strftime('%b %d')} - {period.end_date.strftime('%b %d, %Y')}"
            },
            'recurring_replication': {
                'groups_created': replication_result['groups_created'],
                'transactions_created': replication_result['transactions_created']
            }
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=400)


@login_required
def get_period_details_ajax(request):
    """AJAX: Returns details and summary of a specific period."""
    try:
        period_start_str = request.GET.get('period_start')

        family, current_member, _unused = get_family_context(request.user)
        if not family:
            return JsonResponse({'status': 'error', 'error': _('User not in family')}, status=403)

        # Only ADMIN and PARENT can view period details for deletion
        if current_member.role not in ['ADMIN', 'PARENT']:
            return JsonResponse({'status': 'error', 'error': 'Permission denied'}, status=403)

        # Parse period start date
        period_start = dt_datetime.strptime(period_start_str, '%Y-%m-%d').date()

        # Get current period to check if this is current
        current_start, current_end, _unused = get_current_period_dates(family, None)
        is_current_period = (period_start == current_start)

        # Get period dates
        start_date, end_date, period_label = get_current_period_dates(family, period_start_str)

        # Count FlowGroups
        flow_groups = FlowGroup.objects.filter(
            family=family,
            period_start_date=period_start
        )
        flow_group_count = flow_groups.count()

        # Count Transactions
        transaction_count = Transaction.objects.filter(
            flow_group__in=flow_groups
        ).count()

        # Calculate key metrics
        income_transactions = Transaction.objects.filter(
            flow_group__family=family,
            flow_group__period_start_date=period_start,
            flow_group__group_type=FLOW_TYPE_INCOME,
            date__range=(start_date, end_date)
        )

        from ..models import EXPENSE_MAIN, EXPENSE_SECONDARY
        expense_transactions = Transaction.objects.filter(
            flow_group__family=family,
            flow_group__period_start_date=period_start,
            flow_group__group_type__in=[EXPENSE_MAIN, EXPENSE_SECONDARY],
            date__range=(start_date, end_date)
        )

        # Total income
        total_income_agg = income_transactions.aggregate(
            estimated=Sum('amount'),
            realized=Sum('amount', filter=Q(realized=True))
        )

        total_income_estimated = total_income_agg['estimated']
        total_income_realized = total_income_agg['realized']

        if total_income_estimated:
            total_income_estimated = Decimal(str(total_income_estimated.amount)) if hasattr(total_income_estimated, 'amount') else total_income_estimated
        else:
            total_income_estimated = Decimal('0.00')

        if total_income_realized:
            total_income_realized = Decimal(str(total_income_realized.amount)) if hasattr(total_income_realized, 'amount') else total_income_realized
        else:
            total_income_realized = Decimal('0.00')

        # Total expenses
        total_expense_agg = expense_transactions.aggregate(
            estimated=Sum('amount'),
            realized=Sum('amount', filter=Q(realized=True))
        )

        total_expense_estimated = total_expense_agg['estimated']
        total_expense_realized = total_expense_agg['realized']

        if total_expense_estimated:
            total_expense_estimated = Decimal(str(total_expense_estimated.amount)) if hasattr(total_expense_estimated, 'amount') else total_expense_estimated
        else:
            total_expense_estimated = Decimal('0.00')

        if total_expense_realized:
            total_expense_realized = Decimal(str(total_expense_realized.amount)) if hasattr(total_expense_realized, 'amount') else total_expense_realized
        else:
            total_expense_realized = Decimal('0.00')

        # Get currency
        period_currency = get_period_currency(family, period_start)
        currency_symbol = get_currency_symbol(period_currency)

        return JsonResponse({
            'status': 'success',
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'label': period_label,
                'is_current': is_current_period
            },
            'summary': {
                'flow_group_count': flow_group_count,
                'transaction_count': transaction_count,
                'total_income_estimated': str(total_income_estimated),
                'total_income_realized': str(total_income_realized),
                'total_expense_estimated': str(total_expense_estimated),
                'total_expense_realized': str(total_expense_realized),
                'currency_symbol': currency_symbol
            }
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=400)


@login_required
@require_POST
@db_transaction.atomic
def delete_period_ajax(request):
    """AJAX: Deletes a period or clears current period data."""
    try:
        data = json.loads(request.body)
        period_start_str = data.get('period_start')

        family, current_member, _unused = get_family_context(request.user)
        if not family:
            return JsonResponse({'status': 'error', 'error': _('User not in family')}, status=403)

        # Only ADMIN and PARENT can delete periods
        if current_member.role not in ['ADMIN', 'PARENT']:
            return JsonResponse({'status': 'error', 'error': 'Permission denied'}, status=403)

        # Parse period start date
        period_start = dt_datetime.strptime(period_start_str, '%Y-%m-%d').date()

        # Get current period to check if this is current
        current_start, current_end, _unused = get_current_period_dates(family, None)
        is_current_period = (period_start == current_start)

        if is_current_period:
            # Current period: Clear all FlowGroups and Transactions, but keep Period entry
            flow_groups = FlowGroup.objects.filter(
                family=family,
                period_start_date=period_start
            )

            # Delete transactions first
            transaction_count = Transaction.objects.filter(
                flow_group__in=flow_groups
            ).count()

            Transaction.objects.filter(flow_group__in=flow_groups).delete()

            # Delete flow groups
            flow_group_count = flow_groups.count()
            flow_groups.delete()

            # Delete bank balances for this period
            BankBalance.objects.filter(
                family=family,
                period_start_date=period_start
            ).delete()

            return JsonResponse({
                'status': 'success',
                'action': 'cleared',
                'message': _('Current period cleared: %(groups)s flow groups and %(transactions)s transactions removed') % {
                    'groups': flow_group_count,
                    'transactions': transaction_count
                },
                'redirect': '/'
            })
        else:
            # Past period: Delete everything including Period entry
            flow_groups = FlowGroup.objects.filter(
                family=family,
                period_start_date=period_start
            )

            # Count before deleting
            transaction_count = Transaction.objects.filter(
                flow_group__in=flow_groups
            ).count()
            flow_group_count = flow_groups.count()

            # Delete transactions
            Transaction.objects.filter(flow_group__in=flow_groups).delete()

            # Delete flow groups
            flow_groups.delete()

            # Delete bank balances
            BankBalance.objects.filter(
                family=family,
                period_start_date=period_start
            ).delete()

            # Delete the Period entry itself
            from ..models import Period
            Period.objects.filter(
                family=family,
                start_date=period_start
            ).delete()

            return JsonResponse({
                'status': 'success',
                'action': 'deleted',
                'message': _('Period deleted: %(groups)s flow groups and %(transactions)s transactions removed') % {
                    'groups': flow_group_count,
                    'transactions': transaction_count
                },
                'redirect': '/'
            })

    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=400)


@login_required
def get_balance_summary_ajax(request):
    """
    AJAX: Returns updated balance summary (income, expense, result).
    Used by dashboard to refresh balance after income/expense changes.
    """
    try:
        from .views_utils import get_balance_summary

        family, current_member, family_members = get_family_context(request.user)
        if not family:
            return JsonResponse({'status': 'error', 'error': _('User not in family')}, status=403)

        # Get period from query parameter
        query_period = request.GET.get('period')
        start_date, end_date, _unused = get_current_period_dates(family, query_period)

        # Get balance summary using the new shared function
        balance_data = get_balance_summary(family, current_member, family_members, start_date, end_date)
        summary = balance_data['summary_totals']

        # Get currency symbol for formatting
        period_currency = get_period_currency(family, start_date)
        currency_symbol = get_currency_symbol(period_currency)

        # Return formatted values as strings, maintaining the original structure for the JS
        return JsonResponse({
            'status': 'success',
            'balance': {
                'estimated_income': str(summary['total_budgeted_income']),
                'realized_income': str(summary['total_realized_income']),
                'estimated_expense': str(summary['total_budgeted_expense']),
                'realized_expense': str(summary['total_realized_expense']),
                'estimated_result': str(summary['estimated_result']),
                'realized_result': str(summary['realized_result']),
                'currency_symbol': currency_symbol
            }
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)


@login_required
@require_POST
def toggle_flowgroup_recurring_ajax(request):
    """
    AJAX: Toggle the is_recurring status of a FlowGroup.
    Only ADMIN and PARENT users can toggle recurring status.
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest(_("Not an AJAX request."))

    family, current_member, _unused = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden(_("User is not associated with a family."))

    # Only ADMIN and PARENT can mark groups as recurring
    if current_member.role == 'CHILD':
        return HttpResponseForbidden(_("Children cannot mark groups as recurring."))

    try:
        data = json.loads(request.body)
        flow_group_id = data.get('flow_group_id')

        if not flow_group_id:
            return JsonResponse({'status': 'error', 'error': _('FlowGroup ID is required')}, status=400)

        flow_group = get_object_or_404(FlowGroup, id=flow_group_id)

        # Check access permissions
        if not can_access_flow_group(flow_group, current_member):
            return HttpResponseForbidden(_("You do not have permission to modify this FlowGroup."))

        # Check if trying to unmark a group that has fixed transactions
        if flow_group.is_recurring:
            # User is trying to unmark as recurring
            fixed_transactions_count = flow_group.transactions.filter(is_fixed=True).count()
            if fixed_transactions_count > 0:
                return JsonResponse({
                    'status': 'error',
                    'error': _('Cannot unmark group as recurring while it has fixed transactions. Please unmark all fixed transactions first.'),
                    'fixed_count': fixed_transactions_count
                }, status=400)

        # Toggle the recurring status
        flow_group.is_recurring = not flow_group.is_recurring
        flow_group.save()

        return JsonResponse({
            'status': 'success',
            'is_recurring': flow_group.is_recurring,
            'message': _('Recurring status updated successfully')
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)


@login_required
@require_POST
def toggle_transaction_fixed_ajax(request):
    """
    AJAX: Toggle the is_fixed status of a Transaction.
    When marking first transaction as fixed, automatically marks parent FlowGroup as recurring.
    Only ADMIN and PARENT users can toggle fixed status.
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseBadRequest(_("Not an AJAX request."))

    family, current_member, _unused = get_family_context(request.user)
    if not family:
        return HttpResponseForbidden(_("User is not associated with a family."))

    # Only ADMIN and PARENT can mark transactions as fixed
    if current_member.role == 'CHILD':
        return HttpResponseForbidden(_("Children cannot mark transactions as fixed."))

    try:
        data = json.loads(request.body)
        transaction_id = data.get('transaction_id')

        if not transaction_id:
            return JsonResponse({'status': 'error', 'error': _('Transaction ID is required')}, status=400)

        transaction = get_object_or_404(Transaction, id=transaction_id)
        flow_group = transaction.flow_group

        # Check access permissions
        if not can_access_flow_group(flow_group, current_member):
            return HttpResponseForbidden(_("You do not have permission to modify this transaction."))

        # Toggle the fixed status
        transaction.is_fixed = not transaction.is_fixed
        transaction.save()

        # If this is the first fixed transaction in the group, auto-mark group as recurring
        flow_group_updated = False
        if transaction.is_fixed and not flow_group.is_recurring:
            flow_group.is_recurring = True
            flow_group.save()
            flow_group_updated = True

        return JsonResponse({
            'status': 'success',
            'is_fixed': transaction.is_fixed,
            'flow_group_is_recurring': flow_group.is_recurring,
            'flow_group_updated': flow_group_updated,
            'message': _('Fixed status updated successfully')
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)


@login_required
def health_check_api(request):
    """
    Simple health check endpoint for the updater to verify the server is running.
    Returns 200 OK if the server is responsive and user is authenticated.
    This is used after updates to check if the server has restarted successfully.
    """
    from ..models import SystemVersion
    from django.conf import settings

    try:
        # Try to access the database to ensure it's responsive
        db_version = SystemVersion.get_current_version()

        return JsonResponse({
            'status': 'ok',
            'db_version': db_version or '0.0.0',
            'debug': getattr(settings, 'DEBUG', False)
        })
    except Exception as e:
        # If there's any error, return 503 Service Unavailable
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=503)