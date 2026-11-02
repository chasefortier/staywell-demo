"""Core domain models.

These started life as Django models. When pricing was pulled into its own
module they were flattened into dataclasses so the quote code could run
without a database. The field names still match the old tables.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, Optional


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
class QuoteRequest:
    listing_id: str
    check_in: date
    nights: int
    guests: int
    promo_code: Optional[str] = None
    channel: str = "web"


@dataclass(frozen=True)
class Promo:
    code: str
    pct: int = 0
    fixed: Decimal = Decimal("0")
