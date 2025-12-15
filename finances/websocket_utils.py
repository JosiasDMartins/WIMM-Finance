from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
from datetime import datetime
from decimal import Decimal


class WebSocketBroadcaster:
    """Helper class for broadcasting messages to WebSocket clients"""

    @staticmethod
    def broadcast_to_family(family_id, message_type, data, actor_user=None):
        """
        Broadcast a message to all members of a family.

        Args:
            family_id: ID of the family to broadcast to
            message_type: Type of message (e.g., 'transaction_created')
            data: Dictionary with message data
            actor_user: User who triggered the action (optional)
        """
        channel_layer = get_channel_layer()

        if not channel_layer:
            # Channel layer not configured (dev mode without Redis)
            return

        group_name = f'family_{family_id}'

        message = {
            'type': message_type,
            'timestamp': datetime.now().isoformat(),
            'data': data
        }

        if actor_user:
            message['actor'] = {
                'id': actor_user.id,
                'username': actor_user.username
            }

        # Convert Decimal to float for JSON serialization
        message = json.loads(
            json.dumps(message, default=str)
        )

        try:
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'send_update',  # Calls send_update() in consumer
                    'message': message
                }
            )
        except Exception as e:
            # Log error but don't crash the request
            print(f"[WebSocket] Broadcast error: {e}")
            import traceback
            traceback.print_exc()

    @staticmethod
    def broadcast_transaction_created(transaction, actor_user):
        """Broadcast transaction creation"""
        from .views.views_utils import get_currency_symbol

        # Extract numeric amount and currency code
        amount_value = str(transaction.amount.amount)
        currency_code = transaction.amount.currency.code
        currency_symbol = get_currency_symbol(currency_code)

        WebSocketBroadcaster.broadcast_to_family(
            family_id=transaction.flow_group.family.id,
            message_type='transaction_created',
            data={
                'id': transaction.id,
                'description': transaction.description,
                'amount': amount_value,
                'currency': currency_code,
                'currency_symbol': currency_symbol,
                'date': transaction.date.isoformat(),
                'realized': transaction.realized,
                'is_income': transaction.flow_group.group_type == 'INCOME',
                'is_investment': transaction.flow_group.is_investment,
                'is_fixed': getattr(transaction, 'is_fixed', False),
                'flow_group': {
                    'id': transaction.flow_group.id,
                    'name': transaction.flow_group.name,
                    'type': transaction.flow_group.group_type,
                },
                'member': transaction.member.user.username if transaction.member else None,
                'member_id': transaction.member.id if transaction.member else None,
            },
            actor_user=actor_user
        )

    @staticmethod
    def broadcast_transaction_updated(transaction, actor_user):
        """Broadcast transaction update"""
        from .views.views_utils import get_currency_symbol

        # Extract numeric amount and currency code
        amount_value = str(transaction.amount.amount)
        currency_code = transaction.amount.currency.code
        currency_symbol = get_currency_symbol(currency_code)

        WebSocketBroadcaster.broadcast_to_family(
            family_id=transaction.flow_group.family.id,
            message_type='transaction_updated',
            data={
                'id': transaction.id,
                'description': transaction.description,
                'amount': amount_value,
                'currency': currency_code,
                'currency_symbol': currency_symbol,
                'date': transaction.date.isoformat(),
                'realized': transaction.realized,
                'is_income': transaction.flow_group.group_type == 'INCOME',
                'is_investment': transaction.flow_group.is_investment,
                'is_fixed': getattr(transaction, 'is_fixed', False),
                'flow_group': {
                    'id': transaction.flow_group.id,
                    'name': transaction.flow_group.name,
                    'type': transaction.flow_group.group_type,
                },
                'member': transaction.member.user.username if transaction.member else None,
                'member_id': transaction.member.id if transaction.member else None,
            },
            actor_user=actor_user
        )

    @staticmethod
    def broadcast_transaction_deleted(transaction_id, family_id, is_investment=False, actor_user=None):
        """Broadcast transaction deletion"""
        WebSocketBroadcaster.broadcast_to_family(
            family_id=family_id,
            message_type='transaction_deleted',
            data={
                'id': transaction_id,
                'is_investment': is_investment,
            },
            actor_user=actor_user
        )

    @staticmethod
    def broadcast_flowgroup_updated(flowgroup, actor_user):
        """Broadcast FlowGroup update"""
        from decimal import Decimal
        from django.db.models import Sum, Q

        # Calculate totals for this FlowGroup
        estimated_total = Decimal('0.00')
        realized_total = Decimal('0.00')

        transactions = flowgroup.transactions.all()
        for transaction in transactions:
            amount = transaction.amount.amount
            estimated_total += amount
            if transaction.realized:
                realized_total += amount

        # Prepare assigned members and children lists
        assigned_members = list(flowgroup.assigned_members.values_list('id', flat=True))
        assigned_children = list(flowgroup.assigned_children.values_list('id', flat=True))

        WebSocketBroadcaster.broadcast_to_family(
            family_id=flowgroup.family.id,
            message_type='flowgroup_updated',
            data={
                'id': flowgroup.id,
                'name': flowgroup.name,
                'budgeted_amount': str(flowgroup.budgeted_amount.amount) if flowgroup.budgeted_amount else '0.00',
                'currency': flowgroup.budgeted_amount.currency.code if flowgroup.budgeted_amount else '',
                'total_estimated': str(estimated_total),
                'total_realized': str(realized_total),
                'is_shared': flowgroup.is_shared,
                'is_kids_group': flowgroup.is_kids_group,
                'is_investment': flowgroup.is_investment,
                'is_credit_card': flowgroup.is_credit_card,
                'is_recurring': flowgroup.is_recurring,
                'realized': flowgroup.realized,  # For kids groups
                'closed': flowgroup.closed if hasattr(flowgroup, 'closed') else False,  # For credit cards
                'assigned_members': assigned_members,
                'assigned_children': assigned_children,
            },
            actor_user=actor_user
        )

    @staticmethod
    def broadcast_bank_balance_updated(bank_balance, actor_user):
        """Broadcast bank balance update"""
        WebSocketBroadcaster.broadcast_to_family(
            family_id=bank_balance.family.id,
            message_type='bank_balance_updated',
            data={
                'id': bank_balance.id,
                'description': bank_balance.description,
                'amount': str(bank_balance.amount.amount),
                'date': bank_balance.date.strftime('%Y-%m-%d'),
                'member_id': bank_balance.member.id if bank_balance.member else None,
                'member_name': bank_balance.member.user.username if bank_balance.member else 'Family',
            },
            actor_user=actor_user
        )

    @staticmethod
    def broadcast_notification(family_id, title, message, level='info'):
        """
        Broadcast a notification to all family members

        Args:
            family_id: ID of the family
            title: Notification title
            message: Notification message
            level: Notification level (info, success, warning, error)
        """
        WebSocketBroadcaster.broadcast_to_family(
            family_id=family_id,
            message_type='notification',
            data={
                'title': title,
                'message': message,
                'level': level
            },
            actor_user=None
        )

    @staticmethod
    def broadcast_configuration_updated(family_configuration, actor_user):
        """Broadcast family configuration update"""
        WebSocketBroadcaster.broadcast_to_family(
            family_id=family_configuration.family.id,
            message_type='configuration_updated',
            data={
                'base_currency': family_configuration.base_currency,
                'period_type': family_configuration.period_type,
                'starting_day': family_configuration.starting_day,
                'base_date': family_configuration.base_date.strftime('%Y-%m-%d') if family_configuration.base_date else None,
                'bank_reconciliation_tolerance': str(family_configuration.bank_reconciliation_tolerance),
            },
            actor_user=actor_user
        )

    @staticmethod
    def broadcast_member_added(member, actor_user):
        """Broadcast new family member addition"""
        WebSocketBroadcaster.broadcast_to_family(
            family_id=member.family.id,
            message_type='member_added',
            data={
                'id': member.id,
                'username': member.user.username,
                'email': member.user.email or '',
                'role': member.role,
                'role_display': member.get_role_display(),
            },
            actor_user=actor_user
        )

    @staticmethod
    def broadcast_member_updated(member, actor_user):
        """Broadcast family member update"""
        WebSocketBroadcaster.broadcast_to_family(
            family_id=member.family.id,
            message_type='member_updated',
            data={
                'id': member.id,
                'username': member.user.username,
                'email': member.user.email or '',
                'role': member.role,
                'role_display': member.get_role_display(),
            },
            actor_user=actor_user
        )

    @staticmethod
    def broadcast_member_removed(member_id, family_id, username, actor_user):
        """Broadcast family member removal"""
        WebSocketBroadcaster.broadcast_to_family(
            family_id=family_id,
            message_type='member_removed',
            data={
                'id': member_id,
                'username': username,
            },
            actor_user=actor_user
        )
