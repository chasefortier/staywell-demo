"""Pure quote engine.

Calculation order and rounding mirror the legacy engine exactly, quirks included.
See docs/quirks.md before changing anything here.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from quote_service import jurisdictions
from quote_service.catalog import get_listing
from quote_service.models import Listing, Quote, QuoteRequest
from quote_service.promos import find_promo

CENT = Decimal("0.01")
ZERO = Decimal("0")

SEASONAL_CAP = Decimal("1.5")
WEEKEND_MULTIPLIER = Decimal("1.15")
WEEKEND_DAYS = (4, 5)  # nights starting Friday or Saturday
EXTRA_GUEST_NIGHTLY_CAP = Decimal("75")
SERVICE_FEE_RATE = Decimal("0.142")
PARTNER_COMMISSION = Decimal("0.12")
WEEKLY_NIGHTS = 7
MONTHLY_NIGHTS = 28


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def nightly_rates(listing: Listing, request: QuoteRequest) -> list:
    rates = []
    for i in range(request.nights):
        night = request.check_in + timedelta(days=i)
        multiplier = listing.seasonal_multipliers.get(night.month, Decimal("1"))
        multiplier = min(multiplier, SEASONAL_CAP)
        # The weekend uplift is applied after the cap, so it can push past 1.5x.
        if night.weekday() in WEEKEND_DAYS:
            multiplier = multiplier * WEEKEND_MULTIPLIER
        # Built-in round() on a Decimal rounds halves to even (264.5 -> 264).
        # Legacy behavior: never replace this with half-up quantization.
        rates.append(Decimal(round(listing.nightly_rate * multiplier)))
    return rates


def calculate_quote(listing: Listing, request: QuoteRequest) -> Quote:
    nightly = nightly_rates(listing, request)
    lodging_subtotal = sum(nightly, ZERO)

    stay_pct = 0
    if request.nights >= MONTHLY_NIGHTS:
        stay_pct = listing.monthly_discount_pct
    elif request.nights >= WEEKLY_NIGHTS:
        stay_pct = listing.weekly_discount_pct
    promo = find_promo(request.promo_code)
    pct = max(stay_pct, promo.pct if promo else 0)
    discount = money(lodging_subtotal * pct / 100)
    if promo and promo.fixed:
        discount += promo.fixed
    discount = min(discount, lodging_subtotal)
    lodging = lodging_subtotal - discount

    cleaning = ZERO if request.nights >= MONTHLY_NIGHTS else listing.cleaning_fee

    extra_guests = max(0, request.guests - listing.included_guests)
    extra_per_night = min(extra_guests * listing.extra_guest_fee, EXTRA_GUEST_NIGHTLY_CAP)
    extra = extra_per_night * request.nights

    if request.channel == "partner":
        lodging = money(lodging * (1 + PARTNER_COMMISSION))
        service_fee = Decimal("0.00")
    else:
        service_fee = money((lodging + cleaning) * SERVICE_FEE_RATE)

    tax = jurisdictions.occupancy_tax(
        listing.jurisdiction, request.nights, lodging, cleaning, extra, service_fee
    )
    total = lodging + cleaning + extra + service_fee + tax

    return Quote(
        listing_id=listing.id,
        nights=request.nights,
        currency="USD",
        nightly_rates=tuple(money(n) for n in nightly),
        lodging_subtotal=money(lodging_subtotal),
        discount=money(discount),
        lodging=money(lodging),
        extra_guest_fee=money(extra),
        cleaning_fee=money(cleaning),
        service_fee=money(service_fee),
        tax=money(tax),
        total=money(total),
    )


def get_quote(request: QuoteRequest) -> Quote:
    """Price a request against the catalog. Raises ListingNotFound for unknown listings."""
    return calculate_quote(get_listing(request.listing_id), request)
