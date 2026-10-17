import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import AttendanceChange, attendance_change_token

logger = logging.getLogger("attendance")


def _send(slug: str, payload: dict) -> None:
    """Send one payload to the meeting's group.

    The live view is not the record: the row this describes is already saved when
    this runs, so a channel layer that is missing, down or refusing has to cost
    the update and never the request. A failure used to turn a saved check-in into
    a 500, which the participant could only answer by trying again and being told
    they were already present. The next page load draws the same state from the
    database.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    try:
        async_to_sync(channel_layer.group_send)(f"attendance_{slug}", payload)
    except Exception:  # noqa: BLE001 - a live update must never fail the write
        logger.exception(f"sending {payload['type']} for attendance event {slug} failed")


def send_attendance_change(slug: str, change: AttendanceChange) -> None:
    _send(
        slug,
        {
            "type": "attendance.change",
            "change": {
                "key": change.attendee_key,
                "name": change.attendee_name,
                "type": change.type_name,
                **attendance_change_token(change),
            },
        },
    )


def send_attendance_invalidate(slug: str) -> None:
    """Tell the meeting's open pages that a row moved outside the public views.

    A correction or a deletion in the admin changes what the database answers
    without producing a change the feed can append, and the page cannot repair
    itself from a snapshot it did not receive. The page reloads instead.
    """
    _send(slug, {"type": "attendance.invalidate"})
