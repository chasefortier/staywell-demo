"""Standard-library HTTP client for the standalone quote service.

Legacy callers use this instead of the in-process pricing engine. It POSTs a
``QuoteRequest`` to ``/v1/quotes`` and returns the structured quote with every
money value and nightly rate decoded directly from its wire string to
``Decimal``.

Configuration:

- Base URL: ``STAYWELL_QUOTE_SERVICE_URL`` (read on every call), default
  ``http://127.0.0.1:8080``. An explicit ``base_url`` argument wins.
- Timeout: finite, default 5 seconds; pass ``timeout=`` to override.

Failures are explicit. A 404 raises the existing ``ListingNotFound``; any
other HTTP status, transport failure, timeout or malformed response raises a
``QuoteServiceError`` subclass. There is no retry and no fallback to the
legacy engine.
"""
from __future__ import annotations

import http.client
import json
import math
import os
import re
import socket
import urllib.error
import urllib.request
from decimal import Decimal

from staywell.listings import ListingNotFound

DEFAULT_BASE_URL = "http://127.0.0.1:8080"
BASE_URL_ENV = "STAYWELL_QUOTE_SERVICE_URL"
DEFAULT_TIMEOUT_SECONDS = 5
QUOTES_PATH = "/v1/quotes"

MONEY_FIELDS = (
    "lodging_subtotal",
    "discount",
    "lodging",
    "extra_guest_fee",
    "cleaning_fee",
    "service_fee",
    "tax",
    "total",
)
_WIRE_MONEY = re.compile(r"-?[0-9]+\.[0-9]{2}")


class QuoteServiceError(Exception):
    """The quote service could not produce a quote."""


class QuoteServiceHTTPError(QuoteServiceError):
    def __init__(self, status, detail, url):
        self.status = status
        self.detail = detail
        self.url = url
        super().__init__(f"quote service returned HTTP {status} for {url}: {detail}")


class QuoteServiceUnavailable(QuoteServiceError):
    """The service could not be reached or the connection failed."""


class QuoteServiceTimeout(QuoteServiceUnavailable):
    """The service did not answer within the timeout."""


class QuoteServiceResponseError(QuoteServiceError):
    """The service answered with a body that is not a valid quote."""


def configured_base_url():
    return os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL


def _validate_base_url(base_url):
    if not re.match(r"https?://[^/]", base_url):
        raise ValueError(f"quote service base URL must be an http(s) URL, got {base_url!r}")
    return base_url.rstrip("/")


def _validate_timeout(timeout):
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise ValueError(f"timeout must be a number of seconds, got {timeout!r}")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError(f"timeout must be finite and positive, got {timeout!r}")
    return timeout


def request_payload(request):
    return {
        "listing_id": request.listing_id,
        "check_in": request.check_in.isoformat(),
        "nights": request.nights,
        "guests": request.guests,
        "promo_code": request.promo_code,
        "channel": request.channel,
    }


def _money(value, field):
    if not isinstance(value, str) or not _WIRE_MONEY.fullmatch(value):
        raise QuoteServiceResponseError(f"{field} must be a two-decimal money string, got {value!r}")
    return Decimal(value)


def decode_quote(body):
    """Convert a ``/v1/quotes`` JSON object into a quote with ``Decimal`` money."""
    if not isinstance(body, dict):
        raise QuoteServiceResponseError(f"quote must be a JSON object, got {type(body).__name__}")
    missing = [name for name in ("listing_id", "nights", "currency", "nightly_rates") + MONEY_FIELDS if name not in body]
    if missing:
        raise QuoteServiceResponseError(f"quote is missing fields: {', '.join(missing)}")
    nights = body["nights"]
    if isinstance(nights, bool) or not isinstance(nights, int):
        raise QuoteServiceResponseError(f"nights must be an integer, got {nights!r}")
    for name in ("listing_id", "currency"):
        if not isinstance(body[name], str):
            raise QuoteServiceResponseError(f"{name} must be a string, got {body[name]!r}")
    rates = body["nightly_rates"]
    if not isinstance(rates, list):
        raise QuoteServiceResponseError(f"nightly_rates must be a list, got {rates!r}")

    quote = {
        "listing_id": body["listing_id"],
        "nights": nights,
        "currency": body["currency"],
        "nightly_rates": [_money(rate, "nightly_rates") for rate in rates],
    }
    for name in MONEY_FIELDS:
        quote[name] = _money(body[name], name)
    return quote


def _error_detail(error):
    try:
        raw = error.read()
    except (OSError, http.client.HTTPException):
        raw = b""
    finally:
        error.close()
    text = raw.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
    except ValueError:
        return text
    if isinstance(parsed, dict) and "detail" in parsed:
        return parsed["detail"]
    return parsed


class QuoteClient:
    def __init__(self, base_url=None, timeout=DEFAULT_TIMEOUT_SECONDS, opener=None):
        self.base_url = _validate_base_url(base_url or configured_base_url())
        self.timeout = _validate_timeout(timeout)
        self._open = opener or urllib.request.urlopen

    @property
    def quotes_url(self):
        return self.base_url + QUOTES_PATH

    def fetch_quote(self, request):
        url = self.quotes_url
        http_request = urllib.request.Request(
            url,
            data=json.dumps(request_payload(request)).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with self._open(http_request, timeout=self.timeout) as response:
                status = response.status
                raw = response.read()
        except urllib.error.HTTPError as error:
            detail = _error_detail(error)
            if error.code == 404:
                raise ListingNotFound(request.listing_id) from error
            raise QuoteServiceHTTPError(error.code, detail, url) from error
        except urllib.error.URLError as error:
            if isinstance(error.reason, socket.timeout):
                raise self._timeout(url) from error
            raise QuoteServiceUnavailable(f"quote service unreachable at {url}: {error.reason}") from error
        except (socket.timeout, TimeoutError) as error:
            raise self._timeout(url) from error
        except (OSError, http.client.HTTPException) as error:
            raise QuoteServiceUnavailable(f"quote service connection failed at {url}: {error!r}") from error

        if status != 200:
            raise QuoteServiceResponseError(f"quote service returned unexpected HTTP {status} for {url}")
        try:
            body = json.loads(raw.decode("utf-8"), parse_float=Decimal)
        except ValueError as error:
            raise QuoteServiceResponseError(f"quote service returned invalid JSON from {url}") from error
        return decode_quote(body)

    def _timeout(self, url):
        return QuoteServiceTimeout(f"quote service at {url} did not answer within {self.timeout} seconds")


def fetch_quote(request, *, timeout=DEFAULT_TIMEOUT_SECONDS):
    """Quote ``request`` through the service at the configured base URL."""
    return QuoteClient(timeout=timeout).fetch_quote(request)
