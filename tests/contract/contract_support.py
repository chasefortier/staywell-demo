"""Shared helpers for the real-HTTP contract suite.

The suite talks to an already-running service (start it with scripts/serve.sh)
and never starts one itself. Frozen cases are read through the repository's
golden-master helper so the contract is never copied or regenerated here.
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from _golden import load_cases, request_from_dict, serialize_quote  # noqa: E402

BASE_URL = os.environ.get("STAYWELL_QUOTE_SERVICE_URL", "http://127.0.0.1:8080").rstrip("/")
QUOTES_PATH = "/v1/quotes"

QUOTE_FIELDS = (
    "listing_id",
    "nights",
    "currency",
    "nightly_rates",
    "lodging_subtotal",
    "discount",
    "lodging",
    "extra_guest_fee",
    "cleaning_fee",
    "service_fee",
    "tax",
    "total",
)
MONEY_FIELDS = QUOTE_FIELDS[4:]
TWO_PLACE_MONEY = re.compile(r"-?[0-9]+\.[0-9]{2}")

CASES = load_cases()
CASES_BY_ID = {case["id"]: case for case in CASES}


def assert_wire_shape(body):
    assert tuple(body) == QUOTE_FIELDS
    assert "summary" not in body
    assert type(body["nights"]) is int
    assert body["currency"] == "USD"
    assert isinstance(body["nightly_rates"], list)
    assert len(body["nightly_rates"]) == body["nights"]
    for value in body["nightly_rates"] + [body[name] for name in MONEY_FIELDS]:
        assert isinstance(value, str) and TWO_PLACE_MONEY.fullmatch(value), value


def legacy_quote(payload):
    """Test-only oracle: the unchanged legacy engine, serialized like the fixture."""
    from staywell.services.pricing import get_quote

    return serialize_quote(get_quote(request_from_dict(payload)))
