import logging
from typing import Any, cast

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.auth import UserLazyObject
from asgiref.sync import sync_to_async

from .models import AttendanceEvent
from .views import AttendanceEventOverview

logger = logging.getLogger("attendance")

class AttendanceConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self) -> None:
        self.user = cast(UserLazyObject, self.scope["user"])
        self.slug = self.scope["url_route"]["kwargs"]["slug"]
        self.group_name = f"attendance_{self.slug}"

        if not await self._is_user_allowed():
            logger.info(f"rejecting connection attempt for user {self.user} as they not allowed to see overview page")
            return await self.close()

        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, code: int) -> None:
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content: Any, **kwargs: Any) -> None:
        if type(content) == dict:
            if "type" in content and content["type"] == "get_code":
                code, until_next = await self._get_code()
                await self.send_json({
                    "type": "code",
                    "code": code,
                    "until_next": until_next,
                })

    async def attendance_change(self, event):
        await self.send_json({
            "type": "attendance_change",
            "data": {
                "name": event["change"]["name"],
                "type": event["change"]["type"],
            },
        })

    async def _get_code(self) -> tuple[int, float]:
        event = await AttendanceEvent.objects.filter(slug=self.slug).aget()
        until_next_step = event.time_until_next_code()
        return event.get_current_code(), until_next_step

    async def _is_user_allowed(self):
        return await sync_to_async(AttendanceEventOverview.is_user_allowed)(self.user)
