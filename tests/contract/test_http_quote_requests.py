import json

import pytest

from contract_support import CASES_BY_ID, QUOTES_PATH, assert_wire_shape, legacy_quote

VALID = {"listing_id": "sf-loft", "check_in": "2026-03-10", "nights": 2, "guests": 2}


def _with(**changes):
    payload = dict(VALID)
    payload.update(changes)
    return payload


def _without(field):
    return {key: value for key, value in VALID.items() if key != field}


INVALID_PAYLOADS = {
    "missing-listing_id": _without("listing_id"),
    "missing-check_in": _without("check_in"),
    "missing-nights": _without("nights"),
    "missing-guests": _without("guests"),
    "empty-object": {},
    "listing_id-int": _with(listing_id=123),
    "listing_id-null": _with(listing_id=None),
    "listing_id-bool": _with(listing_id=True),
    "listing_id-list": _with(listing_id=["sf-loft"]),
    "check_in-null": _with(check_in=None),
    "check_in-int": _with(check_in=20260310),
    "check_in-empty": _with(check_in=""),
    "check_in-slashes": _with(check_in="2026/03/10"),
    "check_in-us-order": _with(check_in="03-10-2026"),
    "check_in-unpadded": _with(check_in="2026-3-10"),
    "check_in-datetime": _with(check_in="2026-03-10T00:00:00"),
    "check_in-trailing-space": _with(check_in="2026-03-10 "),
    "check_in-text": _with(check_in="next tuesday"),
    "check_in-impossible-day": _with(check_in="2026-02-30"),
    "check_in-impossible-month": _with(check_in="2026-13-01"),
    "nights-null": _with(nights=None),
    "nights-true": _with(nights=True),
    "nights-false": _with(nights=False),
    "nights-numeric-string": _with(nights="2"),
    "nights-integral-float": _with(nights=2.0),
    "nights-fractional-float": _with(nights=2.5),
    "nights-list": _with(nights=[2]),
    "nights-zero": _with(nights=0),
    "nights-negative": _with(nights=-1),
    "guests-null": _with(guests=None),
    "guests-true": _with(guests=True),
    "guests-false": _with(guests=False),
    "guests-numeric-string": _with(guests="2"),
    "guests-integral-float": _with(guests=2.0),
    "guests-fractional-float": _with(guests=1.5),
    "guests-zero": _with(guests=0),
    "guests-negative": _with(guests=-3),
    "promo_code-int": _with(promo_code=10),
    "promo_code-bool": _with(promo_code=True),
    "promo_code-list": _with(promo_code=["SUMMER10"]),
    "channel-null": _with(channel=None),
    "channel-unsupported": _with(channel="mobile"),
    "channel-uppercase": _with(channel="WEB"),
    "channel-empty": _with(channel=""),
    "channel-int": _with(channel=1),
    "body-array": [VALID],
    "body-string": "sf-loft",
    "body-null": None,
}

MALFORMED_BODIES = {
    "truncated-json": b'{"listing_id": "sf-loft", "nights": ',
    "not-json": b"listing_id=sf-loft&nights=2",
    "empty-body": b"",
}


@pytest.mark.parametrize("payload", INVALID_PAYLOADS.values(), ids=INVALID_PAYLOADS.keys())
def test_invalid_input_is_rejected_with_422(client, payload):
    response = client.post(
        QUOTES_PATH, content=json.dumps(payload), headers={"content-type": "application/json"}
    )

    assert response.status_code == 422, response.text


@pytest.mark.parametrize("body", MALFORMED_BODIES.values(), ids=MALFORMED_BODIES.keys())
def test_malformed_json_is_rejected_with_422(client, body):
    response = client.post(QUOTES_PATH, content=body, headers={"content-type": "application/json"})

    assert response.status_code == 422, response.text


@pytest.mark.parametrize("listing_id", ["nyc-penthouse", "SF-LOFT", ""])
def test_unknown_listing_returns_404(client, listing_id):
    response = client.post(QUOTES_PATH, json=_with(listing_id=listing_id))

    assert response.status_code == 404, response.text
    assert "detail" in response.json()


DEFAULT_COMBINATIONS = {
    "both-omitted": {},
    "explicit-web": {"channel": "web"},
    "explicit-null-promo": {"promo_code": None},
    "both-explicit": {"channel": "web", "promo_code": None},
}


def test_channel_and_promo_defaults_equal_explicit_web_and_null(client):
    expected = CASES_BY_ID["gm-001"]["expected"]
    quotes = {}
    for name, extra in DEFAULT_COMBINATIONS.items():
        response = client.post(QUOTES_PATH, json=dict(VALID, **extra))
        assert response.status_code == 200, (name, response.text)
        quotes[name] = response.json()

    for name, quote in quotes.items():
        assert quote == expected, name


NO_NEW_RESTRICTIONS = {
    "historical-check-in": {"listing_id": "sf-loft", "check_in": "2015-06-12", "nights": 3, "guests": 2},
    "guests-over-capacity": {"listing_id": "sf-loft", "check_in": "2026-03-10", "nights": 2, "guests": 9},
    "sixty-nights": {"listing_id": "nyc-studio", "check_in": "2026-11-20", "nights": 60, "guests": 2},
}


@pytest.mark.parametrize("payload", NO_NEW_RESTRICTIONS.values(), ids=NO_NEW_RESTRICTIONS.keys())
def test_no_new_booking_restrictions(client, payload):
    response = client.post(QUOTES_PATH, json=payload)

    assert response.status_code == 200, response.text
    assert response.json() == legacy_quote(payload)
    assert_wire_shape(response.json())


def test_requests_do_not_share_calculation_state(client):
    for case_id in ("gm-001", "gm-002", "gm-001"):
        case = CASES_BY_ID[case_id]
        response = client.post(QUOTES_PATH, json=case["request"])
        assert response.status_code == 200, (case_id, response.text)
        assert response.json() == case["expected"], case_id


IGNORED_PROMOS = ["BOGUS", "", "summer10", "Summer10", "SUMMER10 ", "vip12plus", "welcome25"]


@pytest.mark.parametrize("code", IGNORED_PROMOS)
def test_unknown_empty_or_differently_cased_promo_equals_no_promo(client, code):
    # The frozen fixture never sends these codes; this pins the exact-match lookup.
    baseline = client.post(QUOTES_PATH, json=_with(promo_code=None))
    honored = client.post(QUOTES_PATH, json=_with(promo_code="SUMMER10"))
    ignored = client.post(QUOTES_PATH, json=_with(promo_code=code))

    assert baseline.status_code == honored.status_code == ignored.status_code == 200
    assert honored.json() != baseline.json()
    assert ignored.json() == baseline.json()
