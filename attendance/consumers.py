import logging
from typing import Any, cast

from asgiref.sync import sync_to_async
from channels.auth import UserLazyObject
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import AttendanceEvent, attendee_entry
from .views import AttendanceEventOverview

logger = logging.getLogger("attendance")


class AttendanceConsumer(AsyncJsonWebsocketConsumer):
    # Close codes the client understands. Both mean the page cannot come back on
    # its own, so `overview.js` stops retrying instead of asking again every five
    # seconds for something that will never answer.
    NOT_ALLOWED = 4003
    EVENT_GONE = 4004

    async def connect(self) -> None:
        self.user = cast(UserLazyObject, self.scope["user"])
        self.slug = self.scope["url_route"]["kwargs"]["slug"]
        self.group_name = f"attendance_{self.slug}"

        if not await self._is_user_allowed():
            logger.info(f"rejecting connection attempt for user {self.user} as they not allowed to see overview page")
            return await self.close(code=self.NOT_ALLOWED)

        # The event is looked up here because the snapshot below needs it, and
        # because an unknown or deleted slug has to close the socket cleanly. A
        # failed lookup inside the first get_code would close it with an
        # exception instead, and the client would then reconnect every five
        # seconds forever.
        event = await self._get_event()
        if event is None:
            logger.info(f"rejecting connection attempt for unknown attendance event {self.slug}")
            return await self.close(code=self.EVENT_GONE)

        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.accept()

        await self.send_json({"type": "attendance_snapshot", "data": await self._snapshot(event)})

    async def disconnect(self, code: int) -> None:
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content: Any, **kwargs: Any) -> None:
        # The socket hands out the rotating code, so it must not outlive the
        # permission that opened it. A staff member removed from the staff group
        # while their overview page is still open would otherwise keep reading
        # the code until they closed the tab.
        if not await self._is_user_allowed():
            logger.info(f"closing connection for user {self.user} as they are no longer allowed to see overview page")
            return await self.close(code=self.NOT_ALLOWED)

        if isinstance(content, dict):
            if "type" in content and content["type"] == "get_code":
                code = await self._get_code()
                if code is None:
                    logger.info(f"closing connection as attendance event {self.slug} no longer exists")
                    return await self.close(code=self.EVENT_GONE)

                current_code, until_next = code
                await self.send_json(
                    {
                        "type": "code",
                        "code": current_code,
                        "until_next": until_next,
                    }
                )

    async def attendance_change(self, event):
        # Broadcasts arrive from the channel layer, which the check in
        # `receive_json` does not see: without this one a user demoted since they
        # connected would keep reading attendee names until their next message.
        if not await self._is_user_allowed():
            logger.info(f"closing connection for user {self.user} as they are no longer allowed to see overview page")
            return await self.close(code=self.NOT_ALLOWED)

        await self.send_json(
            {
                "type": "attendance_change",
                "data": {
                    "key": event["change"]["key"],
                    "name": event["change"]["name"],
                    "type": event["change"]["type"],
                },
            }
        )

    async def _get_event(self) -> AttendanceEvent | None:
        """The event this socket is for, or None when its slug does not exist."""
        return await AttendanceEvent.objects.filter(slug=self.slug).afirst()

    async def _snapshot(self, event: AttendanceEvent) -> list[dict[str, str]]:
        """The attendees present right now, as entries the page can render.

        Sent on connect because the page is rendered before the socket opens,
        so anything that happened in between would otherwise be lost.
        """
        attendees = await sync_to_async(event.present_attendees)()
        return [attendee_entry(attendee) for attendee in attendees]

    async def _get_code(self) -> tuple[int, float] | None:
        # Looked up per message rather than cached from connect, so an admin
        # change to the secret or the period reaches an open page at once.
        event = await self._get_event()
        if event is None:
            return None

        return event.get_current_code(), event.time_until_next_code()

    async def _is_user_allowed(self):
        return await sync_to_async(AttendanceEventOverview.is_user_allowed)(self.user)
