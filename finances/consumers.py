import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class UpdateConsumer(AsyncWebsocketConsumer):
    """
    Async WebSocket consumer for real-time family updates.

    Features:
    - Async for high concurrency support
    - Family-based channel groups for isolation
    - Authentication required
    - Automatic reconnection support
    """

    async def connect(self):
        """Handle new WebSocket connection"""
        self.user = self.scope["user"]

        # Reject unauthenticated users
        if not self.user.is_authenticated:
            await self.close()
            return

        # Get family ID using async wrapper
        family_id = await self.get_family_id_for_user()

        if not family_id:
            # User has no family - reject connection
            await self.close()
            return

        self.family_id = family_id
        self.family_group_name = f'family_{self.family_id}'

        # Add to family-specific group
        await self.channel_layer.group_add(
            self.family_group_name,
            self.channel_name
        )

        # Accept the connection
        await self.accept()

        # Log connection for debugging
        print(f"[WebSocket] User {self.user.username} connected to family {self.family_id}")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, 'family_group_name'):
            await self.channel_layer.group_discard(
                self.family_group_name,
                self.channel_name
            )
            print(f"[WebSocket] User {self.user.username} disconnected (code: {close_code})")

    async def receive(self, text_data):
        """
        Handle messages from WebSocket (client -> server)
        Currently used for ping/pong health checks
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'ping':
                # Respond to ping for connection health check
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': data.get('timestamp')
                }))
        except json.JSONDecodeError:
            # Ignore malformed messages
            pass

    async def send_update(self, event):
        """
        Handler called when group receives a message.
        This method is triggered by channel_layer.group_send()
        """
        message = event['message']

        # Send message to WebSocket client
        await self.send(text_data=json.dumps(message))

    # ============================================
    # Database Query Helpers (Async Wrappers)
    # ============================================

    @database_sync_to_async
    def get_family_id_for_user(self):
        """Get family ID for current user (async wrapper)"""
        from finances.models import FamilyMember

        family_member = FamilyMember.objects.select_related('family').filter(
            user=self.user
        ).first()

        if family_member:
            return family_member.family.id
        return None
