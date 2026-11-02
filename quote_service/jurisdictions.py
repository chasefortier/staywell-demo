"""Occupancy tax rules by jurisdiction (invented for the demo, not real tax law)."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Dict

from quote_service.models import JurisdictionRule

CENT = Decimal("0.01")

RULES: Dict[str, JurisdictionRule] = {
    "SF": JurisdictionRule(
        rate=Decimal("0.14"),
        taxes_cleaning=True,
        taxes_service_fee=False,
        exempt_after_nights=None,
        per_night_fee=Decimal("0"),
    ),
    "AUS": JurisdictionRule(
        rate=Decimal("0.17"),
        taxes_cleaning=False,
        taxes_service_fee=False,
        exempt_after_nights=None,
        per_night_fee=Decimal("0"),
    ),
    "NYC": JurisdictionRule(
        rate=Decimal("0.1475"),
        taxes_cleaning=True,
        taxes_service_fee=False,
        exempt_after_nights=30,
        per_night_fee=Decimal("2.00"),
    ),
    "MIA": JurisdictionRule(
        rate=Decimal("0.13"),
        taxes_cleaning=True,
        taxes_service_fee=True,
        exempt_after_nights=None,
        per_night_fee=Decimal("0"),
    ),
}


def occupancy_tax(
    code: str,
    nights: int,
    lodging: Decimal,
    cleaning: Decimal,
    extra_guests: Decimal,
    service_fee: Decimal,
) -> Decimal:
    rule = RULES[code]
    if rule.exempt_after_nights and nights >= rule.exempt_after_nights:
        return Decimal("0.00")
    base = lodging + extra_guests
    if rule.taxes_cleaning:
        base += cleaning
    if rule.taxes_service_fee:
        base += service_fee
    # The percentage is rounded to cents before the flat per-night fee is added.
    tax = (base * rule.rate).quantize(CENT, rounding=ROUND_HALF_UP)
    return tax + rule.per_night_fee * nights
