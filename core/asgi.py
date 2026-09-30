"""
ASGI config for date project.

It exposes the ASGI callable as a module-level variable named ``application``.

The Channels application in ``core.routing`` serves both HTTP and WebSockets;
gunicorn (Uvicorn worker) targets this module in production, while the dev
``runserver`` command (daphne) uses ``ASGI_APPLICATION`` directly.
"""

import asyncio

from django.conf import settings

from core import routing


class HttpConcurrencyLimiter:
    """Bound concurrent HTTP requests without consuming slots for WebSockets."""

    def __init__(self, application, limit: int):
        if limit < 1:
            raise ValueError("ASGI_HTTP_CONCURRENCY must be at least 1")
        self.application = application
        self.limit = limit
        self._semaphore = asyncio.Semaphore(limit)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.application(scope, receive, send)

        async with self._semaphore:
            return await self.application(scope, receive, send)


application = HttpConcurrencyLimiter(
    routing.application,
    settings.ASGI_HTTP_CONCURRENCY,  # type: ignore[misc]  # Custom Django setting.
)

__all__ = ['HttpConcurrencyLimiter', 'application']
