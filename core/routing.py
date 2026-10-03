import os
from importlib import import_module

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.apps import apps
from django.core.asgi import get_asgi_application

proj_name = os.environ.get("PROJECT_NAME", "date")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', f"core.settings.{proj_name}")

# Populate the app registry before importing anything that defines models.
django_asgi_app = get_asgi_application()

# Websocket routes, keyed by the app label that owns them. A variant imports
# only the routing of the apps it installs, so an app left out of
# INSTALLED_APPS never has its consumers or models loaded through here.
WEBSOCKET_ROUTES = {
    'events': 'events.routing',
    'attendance': 'attendance.routing',
}


def websocket_urlpatterns() -> list:
    patterns = []
    for app_label, module in WEBSOCKET_ROUTES.items():
        if apps.is_installed(app_label):
            patterns += import_module(module).websocket_urlpatterns
    return patterns


application = ProtocolTypeRouter(
    {
        'http': django_asgi_app,
        # (http->django views is added by default)
        'websocket': AuthMiddlewareStack(URLRouter(websocket_urlpatterns())),
    }
)
