import logging
from importlib import import_module
from typing import Any

from asgiref.sync import sync_to_async
from channels.auth import get_user
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.contrib.auth.models import AnonymousUser

from .models import AttendanceChange, AttendanceEvent, attendance_change_token, attendee_entry
from .views import AttendanceEventOverview

logger = logging.getLogger("attendance")


class AttendanceConsumer(AsyncJsonWebsocketConsumer):
    # Close codes the client understands. Both mean the page cannot come back on
    # its own, so `overview.js` stops retrying instead of asking again every five
    # seconds for something that will never answer.
    NOT_ALLOWED = 4003
    EVENT_GONE = 4004

    async def connect(self) -> None:
        self.session_key = self.scope["session"].session_key
        self.slug = self.scope["url_route"]["kwargs"]["slug"]
        self.group_name = f"attendance_{self.slug}"

        if not await self._is_user_allowed():
            logger.info(f"rejecting connection attempt for {self.slug}: user is not allowed")
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
        # Re-read the session before every inbound message. The socket can outlive
        # a logout or session rotation in another tab.
        if not await self._is_user_allowed():
            logger.info(f"closing attendance connection for {self.slug}: user is no longer allowed")
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
        # Broadcasts arrive from the channel layer, so they must revalidate the
        # session too before forwarding attendee names.
        if not await self._is_user_allowed():
            logger.info(f"closing attendance connection for {self.slug}: user is no longer allowed")
            return await self.close(code=self.NOT_ALLOWED)

        await self.send_json({"type": "attendance_change", "data": event["change"]})

    async def _get_event(self) -> AttendanceEvent | None:
        """The event this socket is for, or None when its slug does not exist."""
        return await AttendanceEvent.objects.filter(slug=self.slug).afirst()

    async def _snapshot(self, event: AttendanceEvent) -> list[dict[str, str | int | bool]]:
        """All latest attendee states with versions, including absent attendees.

        The page is rendered before the socket opens. Per-attendee versions let
        the browser merge this snapshot with channel messages that race it, while
        absent states act as tombstones for delayed arrivals.
        """
        changes = await sync_to_async(lambda: list(event.latest_attendance_changes()))()
        return [
            {
                **attendee_entry(change.attendee),
                "type": AttendanceChange.Type(change.type).name,
                "present": change.type == AttendanceChange.Type.ENTER,
                **attendance_change_token(change),
            }
            for change in changes
        ]

    async def _get_code(self) -> tuple[int, float] | None:
        # Looked up per message rather than cached from connect, so an admin
        # change to the secret or the period reaches an open page at once.
        event = await self._get_event()
        if event is None:
            return None

        return event.get_current_code(), event.time_until_next_code()

    async def _get_current_user(self):
        """Authenticate against the current server-side session, not connect's cache."""
        if not self.session_key:
            return AnonymousUser()

        session_store = import_module(settings.SESSION_ENGINE).SessionStore
        session = session_store(session_key=self.session_key)
        return await get_user({**self.scope, "session": session})

    async def _is_user_allowed(self) -> bool:
        user = await self._get_current_user()

        def is_allowed() -> bool:
            return bool(getattr(user, "is_active", False) and AttendanceEventOverview.is_user_allowed(user))

        return await sync_to_async(is_allowed)()
