from channels.testing import HttpCommunicator, WebsocketCommunicator
from django.test import SimpleTestCase

from core import routing
from core.asgi import application


class AsgiApplicationTests(SimpleTestCase):
    def test_asgi_exposes_the_channels_application(self):
        self.assertIs(application, routing.application)

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
