"""Stdlib test doubles for the quote service adapter.

Offline unit tests substitute the transport (the ``opener`` that would be
``urllib.request.urlopen``) so no listener or third-party package is needed.
They never replace the real-HTTP parity suite in ``tests/contract``.
"""
import io
import json
from contextlib import contextmanager
from unittest import mock
from urllib.error import HTTPError

from scripts._golden import request_from_dict, serialize_quote
from staywell.adapters import quote_client
from staywell.listings import ListingNotFound

OFFLINE_BASE_URL = "http://quote-service.test"


class FakeResponse:
    def __init__(self, body, status=200, read_error=None):
        self._body = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.status = status
        self._read_error = read_error
        self.closed = False

    def read(self):
        if self._read_error is not None:
            raise self._read_error
        return self._body

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


def http_error(url, status, body):
    payload = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    return HTTPError(url, status, "error", {"content-type": "application/json"}, io.BytesIO(payload))


class RecordingOpener:
    """Callable with ``urlopen``'s signature that records calls and replays one outcome."""

    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append((request, timeout))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome

    @property
    def last_request(self):
        return self.calls[-1][0]

    @property
    def last_payload(self):
        return json.loads(self.last_request.data.decode("utf-8"))


class LegacyEngineTransport:
    """Offline stand-in for ``POST /v1/quotes`` answered by the legacy engine (test-only)."""

    def __init__(self):
        self.calls = []

    def __call__(self, request, timeout):
        from staywell.services.pricing import get_quote

        payload = json.loads(request.data.decode("utf-8"))
        self.calls.append((payload, timeout))
        try:
            quote = get_quote(request_from_dict(payload))
        except ListingNotFound:
            raise http_error(request.full_url, 404, {"detail": f"Unknown listing: {payload['listing_id']}"})
        return FakeResponse(serialize_quote(quote))


@contextmanager
def offline_quote_service():
    """Route ``quote_client.fetch_quote`` through the real client over the offline transport."""
    transport = LegacyEngineTransport()
    client = quote_client.QuoteClient(base_url=OFFLINE_BASE_URL, opener=transport)

    def fetch(request, **_):
        return client.fetch_quote(request)

    with mock.patch.object(quote_client, "fetch_quote", side_effect=fetch):
        yield transport
