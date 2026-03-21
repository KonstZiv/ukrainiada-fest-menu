"""Custom middleware."""

from django.http import HttpRequest, HttpResponseBase
from django.middleware.gzip import GZipMiddleware


class SSEAwareGZipMiddleware(GZipMiddleware):
    """GZipMiddleware that skips text/event-stream responses.

    Gzip compression breaks SSE real-time delivery because the browser
    waits for a complete gzip block before decoding.
    """

    def process_response(
        self, request: HttpRequest, response: HttpResponseBase
    ) -> HttpResponseBase:
        if response.get("Content-Type", "").startswith("text/event-stream"):
            return response
        return super().process_response(request, response)
