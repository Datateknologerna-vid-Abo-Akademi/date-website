from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

import os
import events.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

application = ProtocolTypeRouter({
    'http': get_asgi_application(),

    # (http->django views is added by default)
    'websocket': AuthMiddlewareStack(
            URLRouter(
                events.routing.websocket_urlpatterns
            )
    ),
})
