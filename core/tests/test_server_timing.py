from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from date.middleware import ServerTimingMiddleware


class ServerTimingMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(SERVER_TIMING_ENABLED=False)
    def test_does_not_add_header_when_disabled(self):
        middleware = ServerTimingMiddleware(lambda request: HttpResponse("ok"))

        response = middleware(self.factory.get("/"))

        self.assertNotIn("Server-Timing", response)

    @override_settings(SERVER_TIMING_ENABLED=True)
    def test_adds_app_and_db_metrics_when_enabled(self):
        middleware = ServerTimingMiddleware(lambda request: HttpResponse("ok"))

        response = middleware(self.factory.get("/"))

        header = response["Server-Timing"]
        self.assertIn("app;dur=", header)
        self.assertIn("db;dur=", header)
        self.assertIn('desc="0 queries"', header)

    @override_settings(SERVER_TIMING_ENABLED=True)
    def test_counts_queries_during_request(self):
        def get_response(request):
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return HttpResponse("ok")

        middleware = ServerTimingMiddleware(get_response)

        response = middleware(self.factory.get("/"))

        self.assertIn('desc="1 query"', response["Server-Timing"])
