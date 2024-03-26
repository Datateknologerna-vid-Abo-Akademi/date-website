from channels.generic.websocket import AsyncWebsocketConsumer
import json


class EventConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.event = self.scope['url_route']['kwargs']['event_name']
        self.event_group_name = 'event_%s' % self.event

        # Join event group
        await self.channel_layer.group_add(
            self.event_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, code):
        # Leave event group
        await self.channel_layer.group_discard(
            self.event_group_name,
            self.channel_name
        )

    async def event_message(self, event):
        # Send message
        msg = event['data']
        await self.send(text_data=json.dumps({
            'data': msg
        }))
