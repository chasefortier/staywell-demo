"""Promo codes honored at checkout. Matching is exact and case-sensitive."""
from __future__ import annotations

from decimal import Decimal as D
from typing import Dict, Optional

from quote_service.models import Promo

PROMOS: Dict[str, Promo] = {
    "SUMMER10": Promo(code="SUMMER10", pct=10),
    "FALL15": Promo(code="FALL15", pct=15),
    "WELCOME25": Promo(code="WELCOME25", fixed=D("25")),
    "VIP12PLUS": Promo(code="VIP12PLUS", pct=12, fixed=D("40")),
}


def find_promo(code: Optional[str]) -> Optional[Promo]:
    """Unknown, empty or differently-cased codes silently mean no promo."""
    return PROMOS.get(code) if code else None
