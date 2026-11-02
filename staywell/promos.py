"""Promo codes currently honored at checkout."""
from __future__ import annotations

from decimal import Decimal as D
from typing import Dict

from staywell.models import Promo

PROMOS: Dict[str, Promo] = {
    "SUMMER10": Promo(code="SUMMER10", pct=10),
    "FALL15": Promo(code="FALL15", pct=15),
    "WELCOME25": Promo(code="WELCOME25", fixed=D("25")),
    "VIP12PLUS": Promo(code="VIP12PLUS", pct=12, fixed=D("40")),
}
