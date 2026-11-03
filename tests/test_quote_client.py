import ast
import json
import math
import os
import socket
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import mock
from urllib.error import URLError

from scripts._golden import load_cases, request_from_dict
from staywell.adapters import quote_client
from staywell.adapters.quote_client import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    QuoteClient,
    QuoteServiceError,
    QuoteServiceHTTPError,
    QuoteServiceResponseError,
    QuoteServiceTimeout,
    QuoteServiceUnavailable,
)
from staywell.listings import ListingNotFound
from staywell.models import QuoteRequest
from tests.quote_doubles import FakeResponse, RecordingOpener, http_error

ROOT = Path(__file__).resolve().parent.parent
CASES = load_cases()
QUOTE_FIELDS = (
    "listing_id",
    "nights",
    "currency",
    "nightly_rates",
    "lodging_subtotal",
    "discount",
    "lodging",
    "extra_guest_fee",
    "cleaning_fee",
    "service_fee",
    "tax",
    "total",
)
MONEY_FIELDS = QUOTE_FIELDS[4:]
SAMPLE = QuoteRequest(listing_id="sf-loft", check_in=date(2026, 3, 10), nights=2, guests=2)
SAMPLE_BODY = CASES[0]["expected"]
BASE = "http://quote.test"


def client_for(outcome, **kwargs):
    opener = RecordingOpener(outcome)
    return QuoteClient(base_url=kwargs.pop("base_url", BASE), opener=opener, **kwargs), opener


class RequestSerializationTests(unittest.TestCase):
    def test_posts_every_request_field_as_json_to_v1_quotes(self):
        client, opener = client_for(FakeResponse(SAMPLE_BODY))
        request = QuoteRequest(
            listing_id="mia-villa",
            check_in=date(2027, 1, 5),
            nights=9,
            guests=7,
            promo_code="VIP12PLUS",
            channel="partner",
        )

        client.fetch_quote(request)

        http_request = opener.last_request
        self.assertEqual(http_request.get_method(), "POST")
        self.assertEqual(http_request.full_url, "http://quote.test/v1/quotes")
        self.assertEqual(http_request.get_header("Content-type"), "application/json")
        self.assertEqual(http_request.get_header("Accept"), "application/json")
        self.assertEqual(
            opener.last_payload,
            {
                "listing_id": "mia-villa",
                "check_in": "2027-01-05",
                "nights": 9,
                "guests": 7,
                "promo_code": "VIP12PLUS",
                "channel": "partner",
            },
        )

    def test_dataclass_defaults_are_sent_explicitly(self):
        client, opener = client_for(FakeResponse(SAMPLE_BODY))

        client.fetch_quote(SAMPLE)

        self.assertEqual(
            opener.last_payload,
            {
                "listing_id": "sf-loft",
                "check_in": "2026-03-10",
                "nights": 2,
                "guests": 2,
                "promo_code": None,
                "channel": "web",
            },
        )

    def test_every_frozen_request_round_trips_to_its_wire_form(self):
        for case in CASES:
            with self.subTest(case=case["id"]):
                client, opener = client_for(FakeResponse(case["expected"]))
                client.fetch_quote(request_from_dict(case["request"]))
                self.assertEqual(opener.last_payload, case["request"])


class ResponseDecodingTests(unittest.TestCase):
    def test_every_frozen_body_decodes_money_directly_to_decimal(self):
        for case in CASES:
            with self.subTest(case=case["id"]):
                body = case["expected"]
                client, _ = client_for(FakeResponse(body))
                quote = client.fetch_quote(request_from_dict(case["request"]))

                self.assertEqual(tuple(quote), QUOTE_FIELDS)
                self.assertNotIn("summary", quote)
                self.assertIs(type(quote["listing_id"]), str)
                self.assertIs(type(quote["currency"]), str)
                self.assertIs(type(quote["nights"]), int)
                self.assertEqual(quote["listing_id"], body["listing_id"])
                self.assertEqual(quote["currency"], body["currency"])
                self.assertEqual(quote["nights"], body["nights"])
                for name in MONEY_FIELDS:
                    self.assertIs(type(quote[name]), Decimal, name)
                    self.assertEqual(quote[name], Decimal(body[name]), name)
                    self.assertEqual(str(quote[name]), body[name], name)
                self.assertIs(type(quote["nightly_rates"]), list)
                self.assertEqual(quote["nightly_rates"], [Decimal(rate) for rate in body["nightly_rates"]])
                for rate, wire in zip(quote["nightly_rates"], body["nightly_rates"]):
                    self.assertIs(type(rate), Decimal)
                    self.assertEqual(str(rate), wire)

    def test_money_sent_as_json_number_is_rejected_not_converted_through_float(self):
        for name in ("total", "lodging", "cleaning_fee"):
            with self.subTest(field=name):
                body = json.dumps(SAMPLE_BODY).replace(f'"{name}": "{SAMPLE_BODY[name]}"', f'"{name}": {SAMPLE_BODY[name]}')
                client, _ = client_for(FakeResponse(body.encode("utf-8")))
                with self.assertRaises(QuoteServiceResponseError):
                    client.fetch_quote(SAMPLE)

    def test_nightly_rate_sent_as_json_number_is_rejected(self):
        body = dict(SAMPLE_BODY, nightly_rates=[230, "230.00"])
        client, _ = client_for(FakeResponse(body))
        with self.assertRaises(QuoteServiceResponseError):
            client.fetch_quote(SAMPLE)

    def test_malformed_bodies_fail_explicitly(self):
        bodies = {
            "not-json": b"<html>oops</html>",
            "empty": b"",
            "array": b"[]",
            "missing-total": json.dumps({k: v for k, v in SAMPLE_BODY.items() if k != "total"}).encode(),
            "nights-string": json.dumps(dict(SAMPLE_BODY, nights="2")).encode(),
            "nights-bool": json.dumps(dict(SAMPLE_BODY, nights=True)).encode(),
            "money-three-places": json.dumps(dict(SAMPLE_BODY, total="698.690")).encode(),
            "money-text": json.dumps(dict(SAMPLE_BODY, tax="NaN")).encode(),
            "rates-not-list": json.dumps(dict(SAMPLE_BODY, nightly_rates="230.00")).encode(),
        }
        for name, body in bodies.items():
            with self.subTest(body=name):
                response = FakeResponse(body)
                client, _ = client_for(response)
                with self.assertRaises(QuoteServiceResponseError):
                    client.fetch_quote(SAMPLE)
                self.assertTrue(response.closed)

    def test_non_200_success_status_is_rejected(self):
        client, _ = client_for(FakeResponse(SAMPLE_BODY, status=204))
        with self.assertRaises(QuoteServiceResponseError):
            client.fetch_quote(SAMPLE)

    def test_response_is_closed_after_success(self):
        response = FakeResponse(SAMPLE_BODY)
        client, _ = client_for(response)

        client.fetch_quote(SAMPLE)

        self.assertTrue(response.closed)


class ConfigurationTests(unittest.TestCase):
    def test_default_base_url_and_timeout(self):
        self.assertEqual(DEFAULT_BASE_URL, "http://127.0.0.1:8080")
        self.assertEqual(DEFAULT_TIMEOUT_SECONDS, 5)
        with mock.patch.dict(os.environ, {}, clear=True):
            client = QuoteClient(opener=RecordingOpener(FakeResponse(SAMPLE_BODY)))
            self.assertEqual(client.base_url, "http://127.0.0.1:8080")
            self.assertEqual(client.timeout, 5)
            client.fetch_quote(SAMPLE)
            self.assertEqual(client._open.last_request.full_url, "http://127.0.0.1:8080/v1/quotes")
            self.assertEqual(client._open.calls[-1][1], 5)

    def test_environment_override(self):
        with mock.patch.dict(os.environ, {"STAYWELL_QUOTE_SERVICE_URL": "http://quotes.internal:9000/"}):
            client, opener = client_for(FakeResponse(SAMPLE_BODY), base_url=None)
            client.fetch_quote(SAMPLE)
        self.assertEqual(client.base_url, "http://quotes.internal:9000")
        self.assertEqual(opener.last_request.full_url, "http://quotes.internal:9000/v1/quotes")

    def test_empty_environment_value_uses_default(self):
        with mock.patch.dict(os.environ, {"STAYWELL_QUOTE_SERVICE_URL": ""}):
            self.assertEqual(QuoteClient().base_url, DEFAULT_BASE_URL)

    def test_explicit_base_url_wins_over_environment(self):
        with mock.patch.dict(os.environ, {"STAYWELL_QUOTE_SERVICE_URL": "http://ignored.test"}):
            self.assertEqual(QuoteClient(base_url="http://explicit.test/").base_url, "http://explicit.test")

    def test_base_url_must_be_http(self):
        for value in ("127.0.0.1:8080", "ftp://quote.test", "file:///tmp/quote"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    QuoteClient(base_url=value)

    def test_module_fetch_reads_environment_and_timeout_per_call(self):
        opener = RecordingOpener(FakeResponse(SAMPLE_BODY))
        with mock.patch.object(quote_client.urllib.request, "urlopen", opener):
            with mock.patch.dict(os.environ, {"STAYWELL_QUOTE_SERVICE_URL": "http://first.test"}):
                quote_client.fetch_quote(SAMPLE)
            opener.outcome = FakeResponse(SAMPLE_BODY)
            with mock.patch.dict(os.environ, {"STAYWELL_QUOTE_SERVICE_URL": "http://second.test"}):
                quote_client.fetch_quote(SAMPLE, timeout=0.25)
        self.assertEqual(
            [(request.full_url, timeout) for request, timeout in opener.calls],
            [("http://first.test/v1/quotes", 5), ("http://second.test/v1/quotes", 0.25)],
        )

    def test_injected_timeout_reaches_transport(self):
        client, opener = client_for(FakeResponse(SAMPLE_BODY), timeout=1.5)
        client.fetch_quote(SAMPLE)
        self.assertEqual(opener.calls[-1][1], 1.5)

    def test_timeout_must_be_finite_and_positive(self):
        for value in (None, 0, -1, math.inf, math.nan, True, "5"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    QuoteClient(base_url=BASE, timeout=value)
                with self.assertRaises(ValueError):
                    quote_client.fetch_quote(SAMPLE, timeout=value)


class FailureTests(unittest.TestCase):
    def test_404_maps_to_listing_not_found_and_closes_error_body(self):
        error = http_error(f"{BASE}/v1/quotes", 404, {"detail": "Unknown listing: nyc-penthouse"})
        client, _ = client_for(error)

        with self.assertRaises(ListingNotFound) as raised:
            client.fetch_quote(QuoteRequest("nyc-penthouse", date(2026, 3, 10), 2, 2))

        self.assertEqual(raised.exception.args, ("nyc-penthouse",))
        self.assertIsInstance(raised.exception, KeyError)
        self.assertTrue(error.fp.closed)

    def test_other_http_statuses_fail_explicitly_with_status_and_detail(self):
        for status, body in (
            (422, {"detail": [{"msg": "Input should be greater than 0"}]}),
            (500, b"Internal Server Error"),
            (503, {"detail": "maintenance"}),
        ):
            with self.subTest(status=status):
                error = http_error(f"{BASE}/v1/quotes", status, body)
                client, _ = client_for(error)
                with self.assertRaises(QuoteServiceHTTPError) as raised:
                    client.fetch_quote(SAMPLE)
                self.assertEqual(raised.exception.status, status)
                self.assertNotIsInstance(raised.exception, ListingNotFound)
                self.assertIn(str(status), str(raised.exception))
                self.assertTrue(error.fp.closed)

    def test_422_detail_is_reported(self):
        error = http_error(f"{BASE}/v1/quotes", 422, {"detail": "nights must be positive"})
        client, _ = client_for(error)
        with self.assertRaises(QuoteServiceHTTPError) as raised:
            client.fetch_quote(SAMPLE)
        self.assertEqual(raised.exception.detail, "nights must be positive")

    def test_connection_refused_is_unavailable(self):
        client, _ = client_for(URLError(ConnectionRefusedError(61, "Connection refused")))
        with self.assertRaises(QuoteServiceUnavailable) as raised:
            client.fetch_quote(SAMPLE)
        self.assertNotIsInstance(raised.exception, QuoteServiceTimeout)
        self.assertIn(BASE, str(raised.exception))

    def test_reset_connection_is_unavailable(self):
        client, _ = client_for(ConnectionResetError(54, "Connection reset by peer"))
        with self.assertRaises(QuoteServiceUnavailable):
            client.fetch_quote(SAMPLE)

    def test_connect_and_read_timeouts_are_explicit(self):
        outcomes = {
            "socket-timeout": socket.timeout("timed out"),
            "wrapped-connect-timeout": URLError(socket.timeout("timed out")),
            "timeout-error": TimeoutError("timed out"),
        }
        for name, outcome in outcomes.items():
            with self.subTest(outcome=name):
                client, _ = client_for(outcome, timeout=0.5)
                with self.assertRaises(QuoteServiceTimeout) as raised:
                    client.fetch_quote(SAMPLE)
                self.assertIn("0.5", str(raised.exception))

    def test_timeout_while_reading_body_closes_response(self):
        response = FakeResponse(SAMPLE_BODY, read_error=socket.timeout("timed out"))
        client, _ = client_for(response)
        with self.assertRaises(QuoteServiceTimeout):
            client.fetch_quote(SAMPLE)
        self.assertTrue(response.closed)

    def test_all_service_failures_share_a_base_class(self):
        for cls in (QuoteServiceHTTPError, QuoteServiceUnavailable, QuoteServiceTimeout, QuoteServiceResponseError):
            self.assertTrue(issubclass(cls, QuoteServiceError))

    def test_failures_never_fall_back_to_the_legacy_engine(self):
        outcomes = (
            http_error(f"{BASE}/v1/quotes", 500, b"boom"),
            URLError(ConnectionRefusedError(61, "Connection refused")),
            socket.timeout("timed out"),
            FakeResponse(b"not json"),
        )
        with mock.patch("staywell.services.pricing.QuoteCalculator.call") as legacy:
            for outcome in outcomes:
                with self.subTest(outcome=repr(outcome)):
                    client, _ = client_for(outcome)
                    with self.assertRaises(QuoteServiceError):
                        client.fetch_quote(SAMPLE)
        legacy.assert_not_called()


class AdapterSourceTests(unittest.TestCase):
    SOURCE = ROOT / "staywell" / "adapters" / "quote_client.py"

    def test_adapter_imports_only_stdlib_and_listing_errors(self):
        tree = ast.parse(self.SOURCE.read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module)
        stdlib = {"__future__", "json", "math", "os", "re", "socket", "http.client", "urllib.error", "urllib.request", "decimal"}
        self.assertLessEqual(imported, stdlib | {"staywell.listings"})
        self.assertNotIn("staywell.services.pricing", imported)

    def test_adapter_never_converts_through_float(self):
        source = self.SOURCE.read_text()
        self.assertNotIn("float(", source)
        self.assertNotIn("staywell.services", source)

    def test_adapter_mentions_no_third_party_packages(self):
        source = self.SOURCE.read_text()
        for name in ("httpx", "fastapi", "pydantic", "uvicorn", "pytest", "requests"):
            self.assertNotIn(name, source)


if __name__ == "__main__":
    unittest.main()
