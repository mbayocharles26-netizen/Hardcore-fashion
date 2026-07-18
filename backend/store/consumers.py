import json

from channels.generic.websocket import AsyncWebsocketConsumer


class VendorNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket endpoint: ws/vendor/notifications/
    Each approved vendor joins their own private group: vendor_<vendor_id>
    Messages are pushed by send_vendor_notification() helper below.
    """

    async def connect(self):
        user = self.scope.get('user')
        vendor = getattr(user, 'vendor_profile', None) if user and user.is_authenticated else None

        if not vendor or vendor.status != 'approved':
            await self.close()
            return

        self.group_name = f'vendor_{vendor.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Called by channel layer when a notification is broadcast to this group
    async def vendor_notification(self, event):
        await self.send(text_data=json.dumps(event['payload']))
