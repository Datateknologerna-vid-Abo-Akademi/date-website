from typing import TYPE_CHECKING

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

if TYPE_CHECKING:
    from .models import AttendanceChange

def send_attendance_change(slug: str, change: AttendanceChange):
    channel_layer = get_channel_layer()
    assert channel_layer
    group = f"attendance_{slug}"

    async_to_sync(channel_layer.group_send)(group, {
        "type": "attendance.change",
        "change": {
            "name": change.attendee_name,
            "type": change.type.name,
        },
    })
