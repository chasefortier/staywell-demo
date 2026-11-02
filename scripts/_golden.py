"""Shared helpers for the golden master scripts."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from staywell.models import QuoteRequest  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "golden_master.json"

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


def request_from_dict(data):
    return QuoteRequest(
        listing_id=data["listing_id"],
        check_in=date.fromisoformat(data["check_in"]),
        nights=data["nights"],
        guests=data["guests"],
        promo_code=data.get("promo_code"),
        channel=data.get("channel", "web"),
    )


def serialize_quote(quote):
    out = {
        "listing_id": quote["listing_id"],
        "nights": quote["nights"],
        "currency": quote["currency"],
        "nightly_rates": [str(n) for n in quote["nightly_rates"]],
    }
    for name in MONEY_FIELDS:
        out[name] = str(quote[name])
    return out


def load_cases():
    with FIXTURE.open() as fh:
        return json.load(fh)["cases"]
