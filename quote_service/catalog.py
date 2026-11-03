"""Listing catalog. Rates are whole dollars."""
from __future__ import annotations

from decimal import Decimal as D
from typing import Dict

from quote_service.models import Listing

_LISTINGS = [
    Listing(
        id="sf-loft",
        title="Mission District Loft",
        jurisdiction="SF",
        nightly_rate=D("230"),
        cleaning_fee=D("85"),
        included_guests=2,
        max_guests=4,
        extra_guest_fee=D("30"),
        weekly_discount_pct=8,
        monthly_discount_pct=20,
        seasonal_multipliers={6: D("1.2"), 7: D("1.25"), 8: D("1.25"), 12: D("1.3")},
    ),
    Listing(
        id="sf-victorian",
        title="Painted Lady Victorian",
        jurisdiction="SF",
        nightly_rate=D("315"),
        cleaning_fee=D("140"),
        included_guests=4,
        max_guests=8,
        extra_guest_fee=D("35"),
        weekly_discount_pct=10,
        monthly_discount_pct=25,
        seasonal_multipliers={7: D("1.3"), 8: D("1.3"), 12: D("1.45")},
    ),
    Listing(
        id="aus-bungalow",
        title="South Congress Bungalow",
        jurisdiction="AUS",
        nightly_rate=D("190"),
        cleaning_fee=D("70"),
        included_guests=2,
        max_guests=5,
        extra_guest_fee=D("25"),
        weekly_discount_pct=7,
        monthly_discount_pct=18,
        seasonal_multipliers={3: D("1.6"), 10: D("1.35")},
    ),
    Listing(
        id="aus-ranch",
        title="Hill Country Ranch House",
        jurisdiction="AUS",
        nightly_rate=D("145"),
        cleaning_fee=D("95"),
        included_guests=4,
        max_guests=10,
        extra_guest_fee=D("20"),
        weekly_discount_pct=12,
        monthly_discount_pct=30,
        seasonal_multipliers={3: D("1.8"), 5: D("1.15"), 10: D("1.4")},
    ),
    Listing(
        id="nyc-studio",
        title="West Village Studio",
        jurisdiction="NYC",
        nightly_rate=D("275"),
        cleaning_fee=D("90"),
        included_guests=1,
        max_guests=3,
        extra_guest_fee=D("40"),
        weekly_discount_pct=5,
        monthly_discount_pct=15,
        seasonal_multipliers={9: D("1.1"), 12: D("1.55")},
    ),
    Listing(
        id="nyc-brownstone",
        title="Park Slope Brownstone",
        jurisdiction="NYC",
        nightly_rate=D("410"),
        cleaning_fee=D("160"),
        included_guests=4,
        max_guests=7,
        extra_guest_fee=D("30"),
        weekly_discount_pct=10,
        monthly_discount_pct=22,
        seasonal_multipliers={11: D("1.2"), 12: D("1.5")},
    ),
    Listing(
        id="mia-condo",
        title="Brickell Bay Condo",
        jurisdiction="MIA",
        nightly_rate=D("205"),
        cleaning_fee=D("75"),
        included_guests=2,
        max_guests=4,
        extra_guest_fee=D("30"),
        weekly_discount_pct=6,
        monthly_discount_pct=20,
        seasonal_multipliers={1: D("1.4"), 2: D("1.45"), 3: D("1.5"), 12: D("1.7")},
    ),
    Listing(
        id="mia-villa",
        title="Coconut Grove Villa",
        jurisdiction="MIA",
        nightly_rate=D("530"),
        cleaning_fee=D("250"),
        included_guests=6,
        max_guests=12,
        extra_guest_fee=D("45"),
        weekly_discount_pct=10,
        monthly_discount_pct=25,
        seasonal_multipliers={1: D("1.35"), 2: D("1.5"), 3: D("1.4"), 12: D("1.65")},
    ),
]

LISTINGS: Dict[str, Listing] = {listing.id: listing for listing in _LISTINGS}


class ListingNotFound(LookupError):
    pass


def get_listing(listing_id: str) -> Listing:
    try:
        return LISTINGS[listing_id]
    except KeyError:
        raise ListingNotFound(listing_id) from None
