"""
ASGI config for date project.

It exposes the ASGI callable as a module-level variable named ``application``.

The Channels application in ``core.routing`` serves both HTTP and WebSockets;
gunicorn (Uvicorn worker) targets this module in production, while the dev
``runserver`` command (daphne) uses ``ASGI_APPLICATION`` directly.
"""

from core.routing import application

__all__ = ['application']
