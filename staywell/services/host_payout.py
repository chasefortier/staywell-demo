"""Host payout calculation, run nightly by the payouts job."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from staywell.listings import get_listing
from staywell.services.pricing import QuoteCalculator

HOST_SHARE = Decimal("0.97")
CENT = Decimal("0.01")


class HostPayout:
    def __init__(self, request):
        self.request = request

    def compute(self):
        calculator = QuoteCalculator(get_listing(self.request.listing_id), self.request)
        quote = calculator.call()
        if self.request.channel == "partner":
            # The guest quote's lodging includes commission, which hosts do not earn.
            lodging = quote["lodging_subtotal"] - quote["discount"]
        else:
            lodging = calculator._lodging_total
        base = lodging + quote["cleaning_fee"]
        return (base * HOST_SHARE).quantize(CENT, rounding=ROUND_HALF_UP)
