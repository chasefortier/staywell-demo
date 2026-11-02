"""Shared fixture loading for service tests.

The frozen cases are read through the repository's existing golden-master
helper so every test sees the same, unmodified contract.
"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from _golden import load_cases  # noqa: E402

from quote_service.models import QuoteRequest  # noqa: E402


def frozen_cases():
    return load_cases()


def service_request(data):
    return QuoteRequest(
        listing_id=data["listing_id"],
        check_in=date.fromisoformat(data["check_in"]),
        nights=data["nights"],
        guests=data["guests"],
        promo_code=data.get("promo_code"),
        channel=data.get("channel", "web"),
    )
