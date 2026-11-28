import time
from contextlib import ExitStack

from django.conf import settings
from django.db import close_old_connections, connections
from django.shortcuts import render
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import get_language_from_request

from .language_utils import resolve_language


class ConnectionLifecycleMiddleware:
    """Enforce Django's DB connection lifecycle on the request's own thread.

    This middleware runs on the same thread-sensitive executor thread as
    the sync middleware and views, and runs Django's normal lifecycle
    there before and after the request. Normal Django ASGI request signals
    also perform cleanup, but this outer layer protects exceptional
    disconnect/error paths. Django 6 destroys the executor after each ASGI
    request, so web deployments use CONN_MAX_AGE=0 rather than attempt to
    persist its thread-local connection.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        close_old_connections()
        try:
            response = self.get_response(request)
        finally:
            close_old_connections()
        return response


class LanguageStateMiddleware(MiddlewareMixin):
    @staticmethod
    def process_request(request):
        request._previous_language = translation.get_language()

    @staticmethod
    def process_response(request, response):
        previous_language = getattr(request, "_previous_language", None)
        if previous_language:
            translation.activate(previous_language)
        else:
            translation.deactivate()
        return response


class LangMiddleware(MiddlewareMixin):
    @staticmethod
    def process_request(request):
        # No URL-based language prefixes. Browser language detection is opt-in
        # so first visits start from LANGUAGE_CODE unless a cookie is present.
        if getattr(settings, "USE_ACCEPT_LANGUAGE_HEADER", False):
            lang = get_language_from_request(request, check_path=False)
        else:
            lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        request.LANG = resolve_language(lang)
        translation.activate(request.LANG)
        request.LANGUAGE_CODE = request.LANG


class HTCPCPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        coffe_words = [f"/{x}" for x in ["coffee", "kahvi", "kaffe"]]
        htcpcp_methods = ["BREW", "POST", "BREW", "PROPFIND", "WHEN", "GET"]
        if request.path in coffe_words and request.method in htcpcp_methods:
            return render(request, template_name="core/418.html", status=418)
        return self.get_response(request)


class ServerTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "SERVER_TIMING_ENABLED", False):
            return self.get_response(request)

        db_timing = {"count": 0, "duration": 0.0}
        start = time.perf_counter()

        def wrapper(execute, sql, params, many, context):
            query_start = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                db_timing["count"] += 1
                db_timing["duration"] += (time.perf_counter() - query_start) * 1000

        with ExitStack() as stack:
            for connection in connections.all():
                stack.enter_context(connection.execute_wrapper(wrapper))
            response = self.get_response(request)

        total_duration = (time.perf_counter() - start) * 1000
        query_label = "query" if db_timing["count"] == 1 else "queries"
        response["Server-Timing"] = (
            f"app;dur={total_duration:.1f}, "
            f'db;dur={db_timing['duration']:.1f};desc="{db_timing['count']} {query_label}"'
        )
        return response
