"""Occupancy tax rules by jurisdiction.

NOTE: these rules are invented for the demo and are not real tax law.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")

RULES = {
    "SF": {
        "rate": Decimal("0.14"),
        "taxes_cleaning": True,
        "taxes_service_fee": False,
        "exempt_after_nights": None,
        "per_night_fee": Decimal("0"),
    },
    "AUS": {
        "rate": Decimal("0.17"),
        "taxes_cleaning": False,
        "taxes_service_fee": False,
        "exempt_after_nights": None,
        "per_night_fee": Decimal("0"),
    },
    "NYC": {
        "rate": Decimal("0.1475"),
        "taxes_cleaning": True,
        "taxes_service_fee": False,
        "exempt_after_nights": 30,
        "per_night_fee": Decimal("2.00"),
    },
    "MIA": {
        "rate": Decimal("0.13"),
        "taxes_cleaning": True,
        "taxes_service_fee": True,
        "exempt_after_nights": None,
        "per_night_fee": Decimal("0"),
    },
}


def occupancy_tax(code, nights, lodging, cleaning, extra_guests, service_fee):
    rule = RULES[code]
    if rule["exempt_after_nights"] and nights >= rule["exempt_after_nights"]:
        return Decimal("0.00")
    base = lodging + extra_guests
    if rule["taxes_cleaning"]:
        base += cleaning
    if rule["taxes_service_fee"]:
        base += service_fee
    tax = (base * rule["rate"]).quantize(CENT, rounding=ROUND_HALF_UP)
    return tax + rule["per_night_fee"] * nights
