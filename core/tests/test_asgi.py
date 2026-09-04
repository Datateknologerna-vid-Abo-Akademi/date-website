import asyncio

from channels.testing import HttpCommunicator, WebsocketCommunicator
from django.conf import settings
from django.test import SimpleTestCase

from core import routing
from core.asgi import HttpConcurrencyLimiter, application


class AsgiApplicationTests(SimpleTestCase):
    def test_asgi_wraps_the_channels_application(self):
        self.assertIs(application.application, routing.application)
        self.assertEqual(application.limit, settings.ASGI_HTTP_CONCURRENCY)

    async def test_http_request_served_through_the_asgi_application(self):
        communicator = HttpCommunicator(
            application,
            "GET",
            "/healthz/",
            headers=[(b"host", b"testserver")],
        )
        response = await communicator.get_response()

        self.assertEqual(response["status"], 200)
        self.assertIn(b'"status": "ok"', response["body"])

    async def test_websocket_connects_through_the_asgi_application(self):
        communicator = WebsocketCommunicator(application, "/ws/events/date-test/")
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()


class HttpConcurrencyLimiterTests(SimpleTestCase):
    async def test_bounds_concurrent_http_requests(self):
        release = asyncio.Event()
        two_entered = asyncio.Event()
        active = 0
        maximum_active = 0
        calls = 0

        async def wrapped(scope, receive, send):
            nonlocal active, maximum_active, calls
            calls += 1
            active += 1
            maximum_active = max(maximum_active, active)
            if active == 2:
                two_entered.set()
            await release.wait()
            active -= 1

        limiter = HttpConcurrencyLimiter(wrapped, 2)
        tasks = [asyncio.create_task(limiter({"type": "http"}, None, None)) for _ in range(3)]

        await asyncio.wait_for(two_entered.wait(), timeout=1)
        await asyncio.sleep(0)
        self.assertEqual(calls, 2)

        release.set()
        await asyncio.gather(*tasks)
        self.assertEqual(calls, 3)
        self.assertEqual(maximum_active, 2)

    async def test_releases_slot_after_exception(self):
        calls = 0

        async def wrapped(scope, receive, send):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("request failed")

        limiter = HttpConcurrencyLimiter(wrapped, 1)
        with self.assertRaises(RuntimeError):
            await limiter({"type": "http"}, None, None)
        await asyncio.wait_for(limiter({"type": "http"}, None, None), timeout=1)

    async def test_releases_slot_after_cancellation(self):
        entered = asyncio.Event()
        calls = 0

        async def wrapped(scope, receive, send):
            nonlocal calls
            calls += 1
            if calls == 1:
                entered.set()
                await asyncio.Event().wait()

        limiter = HttpConcurrencyLimiter(wrapped, 1)
        task = asyncio.create_task(limiter({"type": "http"}, None, None))
        await asyncio.wait_for(entered.wait(), timeout=1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        await asyncio.wait_for(limiter({"type": "http"}, None, None), timeout=1)

    async def test_websocket_bypasses_http_limit(self):
        http_entered = asyncio.Event()
        release_http = asyncio.Event()
        websocket_entered = asyncio.Event()

        async def wrapped(scope, receive, send):
            if scope["type"] == "http":
                http_entered.set()
                await release_http.wait()
            else:
                websocket_entered.set()

        limiter = HttpConcurrencyLimiter(wrapped, 1)
        http_task = asyncio.create_task(limiter({"type": "http"}, None, None))
        await asyncio.wait_for(http_entered.wait(), timeout=1)
        await asyncio.wait_for(limiter({"type": "websocket"}, None, None), timeout=1)
        self.assertTrue(websocket_entered.is_set())
        release_http.set()
        await http_task

    def test_rejects_non_positive_limit(self):
        with self.assertRaisesMessage(ValueError, "ASGI_HTTP_CONCURRENCY must be at least 1"):
            HttpConcurrencyLimiter(None, 0)
