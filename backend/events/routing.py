from django.conf import settings
from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/events/(?P<event_name>\w+)/$', consumers.EventConsumer.as_asgi()),
]

# TODO: Fix this in a better way
if settings.PROJECT_NAME == 'on':
    websocket_urlpatterns = [
        re_path(r'ws/(?P<event_name>\w+)/$', consumers.EventConsumer.as_asgi()),
    ]
