import unittest
from datetime import date
from decimal import Decimal

from staywell.models import QuoteRequest
from staywell.services.booking_confirmation import build_confirmation_email
from staywell.services.host_payout import HostPayout
from staywell.services.pricing import get_quote

SAMPLE_STAY = QuoteRequest(listing_id="sf-loft", check_in=date(2026, 3, 10), nights=2, guests=2)


class PricingTests(unittest.TestCase):
    def test_web_quote_for_two_weeknights(self):
        quote = get_quote(SAMPLE_STAY)
        self.assertEqual(quote["total"], Decimal("698.69"))

    def test_confirmation_email_mentions_total(self):
        email = build_confirmation_email("Avery", SAMPLE_STAY)
        self.assertIn("$698.69", email)

    def test_host_payout_for_web_booking(self):
        self.assertEqual(HostPayout(SAMPLE_STAY).compute(), Decimal("528.65"))


if __name__ == "__main__":
    unittest.main()
