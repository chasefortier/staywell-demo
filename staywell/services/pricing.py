"""Legacy quote engine.

Moved here from bookings/views.py in 2018. Website checkout, the mobile app,
host payouts and confirmation emails all go through QuoteCalculator.call().
Talk to pricing before changing anything in here.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from staywell import jurisdictions
from staywell.listings import get_listing
from staywell.promos import PROMOS

CENT = Decimal("0.01")
ZERO = Decimal("0")

SEASONAL_CAP = Decimal("1.5")
WEEKEND_MULTIPLIER = Decimal("1.15")
WEEKEND_DAYS = (4, 5)  # Fri, Sat check-in nights
EXTRA_GUEST_NIGHTLY_CAP = Decimal("75")
SERVICE_FEE_RATE = Decimal("0.142")
PARTNER_COMMISSION = Decimal("0.12")
WEEKLY_NIGHTS = 7
MONTHLY_NIGHTS = 28


def _money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


class QuoteCalculator:
    def __init__(self, listing, request):
        self.listing = listing
        self.request = request
        self._nightly = []
        self._lodging_total = None

    def call(self):
        listing, req = self.listing, self.request

        # (1) seasonal multiplier is capped, weekend uplift goes on after the cap
        for i in range(req.nights):
            night = req.check_in + timedelta(days=i)
            multiplier = listing.seasonal_multipliers.get(night.month, Decimal("1"))
            multiplier = min(multiplier, SEASONAL_CAP)
            if night.weekday() in WEEKEND_DAYS:
                multiplier = multiplier * WEEKEND_MULTIPLIER
            # (7) whole-dollar nights, built-in round()
            self._nightly.append(Decimal(round(listing.nightly_rate * multiplier)))
        lodging_subtotal = sum(self._nightly, ZERO)

        # (2) percentage discounts don't stack: biggest one wins, fixed promo after
        stay_pct = 0
        if req.nights >= MONTHLY_NIGHTS:
            stay_pct = listing.monthly_discount_pct
        elif req.nights >= WEEKLY_NIGHTS:
            stay_pct = listing.weekly_discount_pct
        promo = PROMOS.get(req.promo_code) if req.promo_code else None
        pct = max(stay_pct, promo.pct if promo else 0)
        discount = _money(lodging_subtotal * pct / 100)
        if promo and promo.fixed:
            discount += promo.fixed
        discount = min(discount, lodging_subtotal)
        lodging = lodging_subtotal - discount

        # (3) cleaning is never discounted, and is waived on monthly stays
        cleaning = ZERO if req.nights >= MONTHLY_NIGHTS else listing.cleaning_fee

        # (4) extra guests capped per night, and not part of the service fee base
        extra_guests = max(0, req.guests - listing.included_guests)
        extra_per_night = min(extra_guests * listing.extra_guest_fee, EXTRA_GUEST_NIGHTLY_CAP)
        extra = extra_per_night * req.nights

        # (5) partners: no service fee, commission grossed up into lodging
        if req.channel == "partner":
            lodging = _money(lodging * (1 + PARTNER_COMMISSION))
            service_fee = Decimal("0.00")
        else:
            service_fee = _money((lodging + cleaning) * SERVICE_FEE_RATE)
        self._lodging_total = lodging

        # (6) jurisdiction rules
        tax = jurisdictions.occupancy_tax(
            listing.jurisdiction, req.nights, lodging, cleaning, extra, service_fee
        )

        total = lodging + cleaning + extra + service_fee + tax
        quote = {
            "listing_id": listing.id,
            "nights": req.nights,
            "nightly_rates": [_money(n) for n in self._nightly],
            "lodging_subtotal": _money(lodging_subtotal),
            "discount": _money(discount),
            "lodging": _money(lodging),
            "extra_guest_fee": _money(extra),
            "cleaning_fee": _money(cleaning),
            "service_fee": _money(service_fee),
            "tax": _money(tax),
            "total": _money(total),
            "currency": "USD",
        }
        quote["summary"] = self._summary(quote)
        return quote

    def _summary(self, q):
        nights = q["nights"]
        average = _money(q["lodging"] / nights)
        label = "night" if nights == 1 else "nights"
        return (
            f"{nights} {label} x avg ${average:,} | Cleaning ${q['cleaning_fee']:,}"
            f" | Service ${q['service_fee']:,} | Tax ${q['tax']:,} | Total ${q['total']:,}"
        )


def get_quote(request):
    return QuoteCalculator(get_listing(request.listing_id), request).call()
