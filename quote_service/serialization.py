"""Explicit wire serialization matching the frozen fixture's ``expected`` objects."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from quote_service.models import Quote
from quote_service.pricing import money

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

QUOTE_FIELDS = ("listing_id", "nights", "currency", "nightly_rates") + MONEY_FIELDS


def money_str(value: Decimal) -> str:
    return format(money(value), "f")


def quote_to_dict(quote: Quote) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "listing_id": quote.listing_id,
        "nights": quote.nights,
        "currency": quote.currency,
        "nightly_rates": [money_str(rate) for rate in quote.nightly_rates],
    }
    for name in MONEY_FIELDS:
        out[name] = money_str(getattr(quote, name))
    return out
