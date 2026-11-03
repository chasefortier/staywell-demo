"""Both migrated callers and the stdlib adapter, replayed over real HTTP.

Every frozen request goes through ``staywell.adapters.quote_client`` to the
running service (``STAYWELL_QUOTE_SERVICE_URL``, default
``http://127.0.0.1:8080``). The legacy engine is disabled while production
code runs, so a pass cannot come from an in-process fallback. Oracles are the
frozen original caller copies in ``tests/original_callers.py``.
"""
from datetime import date
from decimal import Decimal

import pytest

from contract_support import CASES, CASES_BY_ID, MONEY_FIELDS, QUOTE_FIELDS, request_from_dict
from staywell.adapters import quote_client
from staywell.adapters.quote_client import QuoteServiceHTTPError
from staywell.listings import ListingNotFound
from staywell.models import QuoteRequest
from staywell.services.booking_confirmation import build_confirmation_email
from staywell.services.host_payout import HostPayout
from staywell.services.pricing import QuoteCalculator
from tests.original_callers import guest_name_for, original_confirmation_email, original_host_payout

CASE_IDS = [case["id"] for case in CASES]
INDEXED_CASES = list(enumerate(CASES))


@pytest.fixture(autouse=True)
def service_is_running(client):
    """Fail fast through the shared reachability check."""


def _refuse_legacy_engine(self):
    raise AssertionError("production caller used the in-process legacy engine")


@pytest.fixture
def disable_legacy_engine(monkeypatch):
    """Call after computing the oracle, which itself needs the legacy engine."""
    return lambda: monkeypatch.setattr(QuoteCalculator, "call", _refuse_legacy_engine)


@pytest.fixture
def legacy_engine_disabled(disable_legacy_engine):
    disable_legacy_engine()


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_adapter_decodes_frozen_quote_over_http(case, legacy_engine_disabled):
    expected = case["expected"]

    quote = quote_client.fetch_quote(request_from_dict(case["request"]))

    assert tuple(quote) == QUOTE_FIELDS
    assert "summary" not in quote
    assert type(quote["listing_id"]) is str and quote["listing_id"] == expected["listing_id"]
    assert type(quote["currency"]) is str and quote["currency"] == expected["currency"]
    assert type(quote["nights"]) is int and quote["nights"] == expected["nights"]
    for name in MONEY_FIELDS:
        assert type(quote[name]) is Decimal, name
        assert quote[name] == Decimal(expected[name]), name
        assert str(quote[name]) == expected[name], name
    assert type(quote["nightly_rates"]) is list
    assert all(type(rate) is Decimal for rate in quote["nightly_rates"])
    assert [str(rate) for rate in quote["nightly_rates"]] == expected["nightly_rates"]


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_host_payout_matches_original_over_http(case, disable_legacy_engine):
    request = request_from_dict(case["request"])
    expected = original_host_payout(request)

    disable_legacy_engine()
    payout = HostPayout(request).compute()

    assert type(payout) is Decimal
    assert payout == expected
    assert str(payout) == str(expected)


@pytest.mark.parametrize("index, case", INDEXED_CASES, ids=CASE_IDS)
def test_confirmation_email_matches_original_over_http(index, case, disable_legacy_engine):
    request = request_from_dict(case["request"])
    name = guest_name_for(index)
    expected = original_confirmation_email(name, request)

    disable_legacy_engine()
    email = build_confirmation_email(name, request)

    assert type(email) is str
    assert email == expected


def test_caller_parity_covers_every_frozen_request():
    assert len(CASES) == 129
    assert len(set(CASE_IDS)) == 129
    assert sum(1 for case in CASES if case["request"]["nights"] == 1) == 8
    assert sum(1 for case in CASES if Decimal(case["expected"]["total"]) >= 1000) == 105


def test_sample_payouts_keep_partner_gap_over_http(legacy_engine_disabled):
    web = HostPayout(request_from_dict(CASES_BY_ID["gm-001"]["request"])).compute()
    partner = HostPayout(request_from_dict(CASES_BY_ID["gm-002"]["request"])).compute()

    assert web == Decimal("528.65")
    assert partner == Decimal("582.19")
    assert partner - web == Decimal("53.54")


@pytest.mark.parametrize(
    "case_id, expected",
    [
        ("gm-001", "Hi Avery, your 2-night stay is confirmed. Total charged: $698.69."),
        ("gm-011", "Hi Avery, your 1-night stay is confirmed. Total charged: $294.79."),
        ("gm-003", "Hi Avery, your 4-night stay is confirmed. Total charged: $1,336.52."),
        ("gm-012", "Hi Avery, your 28-night stay is confirmed. Total charged: $8,623.25."),
    ],
)
def test_sample_emails_over_http(case_id, expected, legacy_engine_disabled):
    request = request_from_dict(CASES_BY_ID[case_id]["request"])

    assert build_confirmation_email("Avery", request) == expected


UNKNOWN = QuoteRequest(listing_id="nyc-penthouse", check_in=date(2026, 3, 10), nights=2, guests=2)
INVALID = QuoteRequest(listing_id="sf-loft", check_in=date(2026, 3, 10), nights=0, guests=2)
CALLERS = {
    "adapter": quote_client.fetch_quote,
    "payout": lambda request: HostPayout(request).compute(),
    "email": lambda request: build_confirmation_email("Avery", request),
}


@pytest.mark.parametrize("caller", CALLERS.values(), ids=CALLERS.keys())
def test_real_404_raises_listing_not_found(caller, legacy_engine_disabled):
    with pytest.raises(ListingNotFound) as raised:
        caller(UNKNOWN)

    assert raised.value.args == ("nyc-penthouse",)


@pytest.mark.parametrize("caller", CALLERS.values(), ids=CALLERS.keys())
def test_real_422_fails_explicitly(caller, legacy_engine_disabled):
    with pytest.raises(QuoteServiceHTTPError) as raised:
        caller(INVALID)

    assert raised.value.status == 422
