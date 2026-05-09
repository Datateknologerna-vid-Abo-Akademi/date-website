from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/attendance/(?P<slug>[-\w]+)$", consumers.AttendanceConsumer.as_asgi())
]
