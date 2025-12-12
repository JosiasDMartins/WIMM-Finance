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
                'is_fixed': getattr(transaction, 'is_fixed', False),
                'flow_group': {
                    'id': transaction.flow_group.id,
                    'name': transaction.flow_group.name,
                    'type': transaction.flow_group.group_type,
                },
                'member': transaction.member.user.username if transaction.member else None,
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
                'is_fixed': getattr(transaction, 'is_fixed', False),
                'flow_group': {
                    'id': transaction.flow_group.id,
                    'name': transaction.flow_group.name,
                    'type': transaction.flow_group.group_type,
                },
                'member': transaction.member.user.username if transaction.member else None,
            },
            actor_user=actor_user
        )

    @staticmethod
    def broadcast_transaction_deleted(transaction_id, family_id, actor_user):
        """Broadcast transaction deletion"""
        WebSocketBroadcaster.broadcast_to_family(
            family_id=family_id,
            message_type='transaction_deleted',
            data={
                'id': transaction_id,
            },
            actor_user=actor_user
        )

    @staticmethod
    def broadcast_flowgroup_updated(flowgroup, actor_user):
        """Broadcast FlowGroup update"""
        WebSocketBroadcaster.broadcast_to_family(
            family_id=flowgroup.family.id,
            message_type='flowgroup_updated',
            data={
                'id': flowgroup.id,
                'name': flowgroup.name,
                'budgeted_amount': str(flowgroup.budgeted_amount) if flowgroup.budgeted_amount else None,
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
                'bank_name': bank_balance.bank_name,
                'balance': str(bank_balance.balance),
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
