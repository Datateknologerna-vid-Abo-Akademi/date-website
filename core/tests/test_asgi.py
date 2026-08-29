from channels.testing import WebsocketCommunicator
from django.test import SimpleTestCase

from core import routing
from core.asgi import application


class AsgiApplicationTests(SimpleTestCase):
    def test_asgi_exposes_the_channels_application(self):
        self.assertIs(application, routing.application)

    async def test_websocket_connects_through_the_asgi_application(self):
        communicator = WebsocketCommunicator(application, "/ws/events/date-test/")
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()
