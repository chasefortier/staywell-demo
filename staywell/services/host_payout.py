"""Host payout calculation, run nightly by the payouts job."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from staywell.adapters import quote_client

HOST_SHARE = Decimal("0.97")
CENT = Decimal("0.01")


class HostPayout:
    def __init__(self, request):
        self.request = request

    def compute(self):
        quote = quote_client.fetch_quote(self.request)
        # Partner lodging already includes the 12% commission gross-up, so
        # partner hosts are paid on it. Preserved pending a human decision; see
        # docs/quirks.md section 9.2.
        base = quote["lodging"] + quote["cleaning_fee"]
        return (base * HOST_SHARE).quantize(CENT, rounding=ROUND_HALF_UP)
