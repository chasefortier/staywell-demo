"""Service-owned domain types."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class Listing:
    id: str
    title: str
    jurisdiction: str
    nightly_rate: Decimal
    cleaning_fee: Decimal
    included_guests: int
    max_guests: int
    extra_guest_fee: Decimal
    weekly_discount_pct: int = 0
    monthly_discount_pct: int = 0
    seasonal_multipliers: Dict[int, Decimal] = field(default_factory=dict)


@dataclass(frozen=True)
class Promo:
    code: str
    pct: int = 0
    fixed: Decimal = Decimal("0")


@dataclass(frozen=True)
class JurisdictionRule:
    rate: Decimal
    taxes_cleaning: bool
    taxes_service_fee: bool
    exempt_after_nights: Optional[int]
    per_night_fee: Decimal


@dataclass(frozen=True)
class QuoteRequest:
    listing_id: str
    check_in: date
    nights: int
    guests: int
    promo_code: Optional[str] = None
    channel: str = "web"


@dataclass(frozen=True)
class Quote:
    """A priced stay. Every money value is a Decimal quantized to cents."""

    listing_id: str
    nights: int
    currency: str
    nightly_rates: Tuple[Decimal, ...]
    lodging_subtotal: Decimal
    discount: Decimal
    lodging: Decimal
    extra_guest_fee: Decimal
    cleaning_fee: Decimal
    service_fee: Decimal
    tax: Decimal
    total: Decimal
