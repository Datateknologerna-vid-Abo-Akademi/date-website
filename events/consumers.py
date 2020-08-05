import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db import models

from .models import Event, EventAttendees
from .views import EventDetailView


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

    async def receive(self, text_data=None, bytes_data=None):
        # Receive message
        text_data_json = json.loads(text_data)
        msg = text_data_json['data']

        await self.channel_layer.group_send(
            self.event_group_name, {
                'type': 'event_message',
                'data': msg
            }
        )

    async def event_message(self, event):
        # Send message
        msg = event['data']
        await self.send(text_data=json.dumps({
            'data': msg
        }))
