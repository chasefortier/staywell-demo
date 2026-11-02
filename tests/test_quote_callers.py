import ast
import inspect
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import mock

from staywell.adapters import quote_client
from staywell.adapters.quote_client import (
    QuoteServiceHTTPError,
    QuoteServiceResponseError,
    QuoteServiceTimeout,
    QuoteServiceUnavailable,
)
from staywell.listings import ListingNotFound
from staywell.models import QuoteRequest
from staywell.services import booking_confirmation, host_payout
from staywell.services.booking_confirmation import build_confirmation_email
from staywell.services.host_payout import HostPayout
from tests.quote_doubles import offline_quote_service

ROOT = Path(__file__).resolve().parent.parent
REQUEST = QuoteRequest(listing_id="sf-loft", check_in=date(2026, 3, 10), nights=2, guests=2)
CALLER_SOURCES = {
    "host_payout": ROOT / "staywell" / "services" / "host_payout.py",
    "booking_confirmation": ROOT / "staywell" / "services" / "booking_confirmation.py",
}


def structured_quote(**overrides):
    quote = {
        "listing_id": "sf-loft",
        "nights": 2,
        "currency": "USD",
        "nightly_rates": [Decimal("230.00"), Decimal("230.00")],
        "lodging_subtotal": Decimal("460.00"),
        "discount": Decimal("0.00"),
        "lodging": Decimal("460.00"),
        "extra_guest_fee": Decimal("0.00"),
        "cleaning_fee": Decimal("85.00"),
        "service_fee": Decimal("77.39"),
        "tax": Decimal("76.30"),
        "total": Decimal("698.69"),
    }
    quote.update(overrides)
    return quote


class StubbedQuote:
    """Patch the public adapter function both callers use."""

    def stub(self, result=None, error=None):
        patcher = mock.patch.object(quote_client, "fetch_quote", return_value=result, side_effect=error)
        fetch = patcher.start()
        self.addCleanup(patcher.stop)
        return fetch


class HostPayoutTests(StubbedQuote, unittest.TestCase):
    def test_public_signature_is_unchanged(self):
        self.assertEqual(list(inspect.signature(HostPayout).parameters), ["request"])
        self.assertEqual(list(inspect.signature(HostPayout(REQUEST).compute).parameters), [])

    def test_quotes_the_request_once_through_the_adapter(self):
        fetch = self.stub(structured_quote())
        self.assertEqual(HostPayout(REQUEST).compute(), Decimal("528.65"))
        fetch.assert_called_once_with(REQUEST)

    def test_base_is_returned_lodging_plus_cleaning_only(self):
        self.stub(
            structured_quote(
                lodging_subtotal=Decimal("9999.00"),
                discount=Decimal("5000.00"),
                lodging=Decimal("1000.00"),
                cleaning_fee=Decimal("100.00"),
                extra_guest_fee=Decimal("750.00"),
                service_fee=Decimal("156.20"),
                tax=Decimal("400.00"),
                total=Decimal("2406.20"),
            )
        )
        self.assertEqual(HostPayout(REQUEST).compute(), Decimal("1067.00"))

    def test_partner_lodging_is_used_as_returned_not_rebuilt_from_subtotal(self):
        self.stub(
            structured_quote(
                lodging_subtotal=Decimal("460.00"),
                discount=Decimal("0.00"),
                lodging=Decimal("515.20"),
                service_fee=Decimal("0.00"),
            )
        )
        self.assertEqual(HostPayout(REQUEST).compute(), Decimal("582.19"))

    def test_cents_round_half_up(self):
        self.stub(structured_quote(lodging=Decimal("0.50"), cleaning_fee=Decimal("0.00")))
        payout = HostPayout(REQUEST).compute()
        self.assertEqual(payout, Decimal("0.49"))
        self.assertIs(type(payout), Decimal)
        self.assertEqual(payout.as_tuple().exponent, -2)

    def test_waived_cleaning_is_zero_in_base(self):
        self.stub(structured_quote(lodging=Decimal("5000.00"), cleaning_fee=Decimal("0.00")))
        self.assertEqual(HostPayout(REQUEST).compute(), Decimal("4850.00"))


class ConfirmationEmailTests(StubbedQuote, unittest.TestCase):
    def test_public_signature_is_unchanged(self):
        self.assertEqual(list(inspect.signature(build_confirmation_email).parameters), ["guest_name", "request"])

    def test_sample_email(self):
        fetch = self.stub(structured_quote())
        self.assertEqual(
            build_confirmation_email("Avery", REQUEST),
            "Hi Avery, your 2-night stay is confirmed. Total charged: $698.69.",
        )
        fetch.assert_called_once_with(REQUEST)

    def test_one_night_wording(self):
        self.stub(structured_quote(nights=1, total=Decimal("294.79")))
        self.assertEqual(
            build_confirmation_email("Avery", REQUEST),
            "Hi Avery, your 1-night stay is confirmed. Total charged: $294.79.",
        )

    def test_totals_are_comma_grouped_with_two_decimals(self):
        for total, text in (
            (Decimal("8623.25"), "$8,623.25."),
            (Decimal("12345.60"), "$12,345.60."),
            (Decimal("1234567.00"), "$1,234,567.00."),
            (Decimal("0.00"), "$0.00."),
        ):
            with self.subTest(total=total):
                self.stub(structured_quote(nights=28, total=total))
                self.assertEqual(
                    build_confirmation_email("Avery", REQUEST),
                    f"Hi Avery, your 28-night stay is confirmed. Total charged: {text}",
                )

    def test_guest_name_is_interpolated_verbatim(self):
        for name in ("María José", "O'Brien-Smith", "Dr. Lee, Jr.", "{guest_name}", "  Sam  ", "", "李雷"):
            with self.subTest(name=name):
                self.stub(structured_quote())
                self.assertEqual(
                    build_confirmation_email(name, REQUEST),
                    f"Hi {name}, your 2-night stay is confirmed. Total charged: $698.69.",
                )

    def test_quote_without_summary_is_enough(self):
        quote = structured_quote()
        self.assertNotIn("summary", quote)
        self.stub(quote)
        self.assertTrue(build_confirmation_email("Avery", REQUEST).endswith("$698.69."))


class FailurePropagationTests(StubbedQuote, unittest.TestCase):
    ERRORS = (
        ListingNotFound("nyc-penthouse"),
        QuoteServiceHTTPError(422, "nights must be positive", "http://quote.test/v1/quotes"),
        QuoteServiceHTTPError(500, "Internal Server Error", "http://quote.test/v1/quotes"),
        QuoteServiceUnavailable("connection refused"),
        QuoteServiceTimeout("timed out"),
        QuoteServiceResponseError("bad body"),
    )

    def test_both_callers_propagate_adapter_failures_without_legacy_fallback(self):
        callers = {
            "payout": lambda: HostPayout(REQUEST).compute(),
            "email": lambda: build_confirmation_email("Avery", REQUEST),
        }
        with mock.patch("staywell.services.pricing.QuoteCalculator.call") as legacy:
            for error in self.ERRORS:
                for name, call in callers.items():
                    with self.subTest(caller=name, error=repr(error)):
                        self.stub(error=error)
                        with self.assertRaises(type(error)) as raised:
                            call()
                        self.assertIs(raised.exception, error)
        legacy.assert_not_called()

    def test_unknown_listing_through_offline_transport_raises_listing_not_found(self):
        request = QuoteRequest(listing_id="nyc-penthouse", check_in=date(2026, 3, 10), nights=2, guests=2)
        with offline_quote_service():
            with self.assertRaises(ListingNotFound):
                HostPayout(request).compute()
            with self.assertRaises(ListingNotFound):
                build_confirmation_email("Avery", request)


class ProductionCouplingTests(unittest.TestCase):
    FORBIDDEN_NAMES = {"QuoteCalculator", "_lodging_total", "get_quote", "summary", "SUMMARY_PATTERN"}

    def test_callers_import_only_the_quote_adapter(self):
        for name, path in CALLER_SOURCES.items():
            with self.subTest(module=name):
                tree = ast.parse(path.read_text())
                imported = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imported.update(alias.name for alias in node.names)
                    elif isinstance(node, ast.ImportFrom):
                        imported.update(f"{node.module}.{alias.name}" for alias in node.names)
                self.assertLessEqual(
                    imported,
                    {"__future__.annotations", "decimal.ROUND_HALF_UP", "decimal.Decimal", "staywell.adapters.quote_client"},
                )

    def test_callers_do_not_touch_calculator_state_or_summary(self):
        for name, path in CALLER_SOURCES.items():
            with self.subTest(module=name):
                tree = ast.parse(path.read_text())
                used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
                used |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
                used |= {
                    node.value
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)
                }
                self.assertFalse(used & self.FORBIDDEN_NAMES, used & self.FORBIDDEN_NAMES)

    def test_caller_modules_do_not_hold_pricing_or_regex_modules(self):
        for module in (host_payout, booking_confirmation):
            with self.subTest(module=module.__name__):
                self.assertFalse(hasattr(module, "QuoteCalculator"))
                self.assertFalse(hasattr(module, "get_quote"))
                self.assertFalse(hasattr(module, "re"))
                self.assertIs(module.quote_client, quote_client)


if __name__ == "__main__":
    unittest.main()
