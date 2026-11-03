"""Focused rule tests using test-local listings and requests.

These cover branches the frozen fixture does not reach (fixed-promo clamp,
unknown or differently-cased promo codes) and pin the order-sensitive steps.
"""
from dataclasses import replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest

from quote_service.catalog import ListingNotFound, get_listing
from quote_service.jurisdictions import occupancy_tax
from quote_service.models import Listing, QuoteRequest
from quote_service.pricing import calculate_quote, get_quote
from quote_service.serialization import QUOTE_FIELDS, quote_to_dict

D = Decimal
MONDAY = date(2026, 1, 5)
THURSDAY = date(2026, 1, 8)
FRIDAY = date(2026, 1, 9)

BASE = Listing(
    id="test-listing",
    title="Test Listing",
    jurisdiction="AUS",
    nightly_rate=D("100"),
    cleaning_fee=D("50"),
    included_guests=2,
    max_guests=4,
    extra_guest_fee=D("10"),
)


def listing(**overrides):
    return replace(BASE, **overrides)


def request(nights=1, check_in=MONDAY, guests=2, promo_code=None, channel="web", listing_id="test-listing"):
    return QuoteRequest(
        listing_id=listing_id,
        check_in=check_in,
        nights=nights,
        guests=guests,
        promo_code=promo_code,
        channel=channel,
    )


def test_weekend_ties_round_half_to_even():
    quote = calculate_quote(listing(nightly_rate=D("190")), request(nights=2, check_in=FRIDAY))
    assert quote.nightly_rates == (D("218"), D("218"))
    quote = calculate_quote(listing(nightly_rate=D("250")), request(nights=2, check_in=FRIDAY))
    assert quote.nightly_rates == (D("288"), D("288"))
    assert all(isinstance(rate, Decimal) for rate in quote.nightly_rates)


def test_half_up_would_differ_for_tie():
    # Guards against a "fix" to half-up nightly rounding.
    value = D("190") * D("1.15")
    assert value == D("218.5")
    assert value.quantize(D("1"), rounding=ROUND_HALF_UP) == D("219")
    quote = calculate_quote(listing(nightly_rate=D("190")), request(check_in=FRIDAY))
    assert quote.nightly_rates == (D("218"),)


def test_subtotal_sums_already_rounded_nights():
    quote = calculate_quote(listing(nightly_rate=D("190")), request(nights=3, check_in=THURSDAY))
    assert quote.nightly_rates == (D("190"), D("218"), D("218"))
    assert quote.lodging_subtotal == D("626")


def test_seasonal_cap_applies_before_weekend_uplift():
    capped = listing(seasonal_multipliers={1: D("2.0")})
    quote = calculate_quote(capped, request(nights=2, check_in=THURSDAY))
    # Thursday: 100 * 1.5. Friday: 100 * 1.5 * 1.15 = 172.5 -> 172 (not 150).
    assert quote.nightly_rates == (D("150"), D("172"))


def test_uplift_above_cap_is_not_recapped():
    quote = calculate_quote(listing(seasonal_multipliers={1: D("1.4")}), request(check_in=FRIDAY))
    assert quote.nightly_rates == (D("161"),)


def test_multiplier_uses_month_of_each_night():
    seasonal = listing(seasonal_multipliers={4: D("1.2")})
    quote = calculate_quote(seasonal, request(nights=2, check_in=date(2026, 3, 31)))
    assert quote.nightly_rates == (D("100"), D("120"))


@pytest.mark.parametrize(
    "nights,expected_pct",
    [(6, 0), (7, 10), (27, 10), (28, 20)],
)
def test_weekly_and_monthly_thresholds(nights, expected_pct):
    discounted = listing(weekly_discount_pct=10, monthly_discount_pct=20)
    quote = calculate_quote(discounted, request(nights=nights))
    assert quote.discount == (quote.lodging_subtotal * expected_pct / 100).quantize(D("0.01"))


# Seven nights from Monday include Friday and Saturday at 115, so the subtotal is 730.
@pytest.mark.parametrize(
    "weekly_pct,promo,expected_discount",
    [
        (10, "SUMMER10", D("73.00")),
        (10, "FALL15", D("109.50")),
        (20, "FALL15", D("146.00")),
        (15, "VIP12PLUS", D("149.50")),
        (10, "WELCOME25", D("98.00")),
    ],
)
def test_largest_percentage_wins_then_fixed_amount_stacks(weekly_pct, promo, expected_discount):
    quote = calculate_quote(listing(weekly_discount_pct=weekly_pct), request(nights=7, promo_code=promo))
    assert quote.lodging_subtotal == D("730")
    assert quote.discount == expected_discount
    assert quote.lodging == D("730") - expected_discount


def test_fixed_promo_discount_is_clamped_to_subtotal():
    cheap = listing(nightly_rate=D("20"))
    quote = calculate_quote(cheap, request(promo_code="WELCOME25"))
    assert quote.lodging_subtotal == D("20")
    assert quote.discount == D("20.00")
    assert quote.lodging == D("0.00")
    assert quote.cleaning_fee == D("50.00")
    assert quote.service_fee == D("7.10")
    assert quote.tax == D("0.00")
    assert quote.total == D("57.10")


def test_clamped_partner_quote_grosses_up_zero_lodging():
    cheap = listing(nightly_rate=D("20"))
    quote = calculate_quote(cheap, request(promo_code="WELCOME25", channel="partner"))
    assert quote.discount == D("20.00")
    assert quote.lodging == D("0.00")
    assert quote.service_fee == D("0.00")
    assert quote.total == D("50.00")


@pytest.mark.parametrize("code", ["", "summer10", "Summer10", "SUMMER10 ", "NOPE"])
def test_unknown_empty_or_differently_cased_promo_is_ignored(code):
    discounted = listing(weekly_discount_pct=5)
    baseline = quote_to_dict(calculate_quote(discounted, request(nights=7)))
    assert quote_to_dict(calculate_quote(discounted, request(nights=7, promo_code=code))) == baseline


def test_promo_percentage_applies_without_stay_discount():
    quote = calculate_quote(listing(), request(nights=1, promo_code="SUMMER10"))
    assert quote.discount == D("10.00")


@pytest.mark.parametrize("nights,expected_cleaning", [(27, D("50.00")), (28, D("0.00"))])
def test_cleaning_waived_at_monthly_and_never_discounted(nights, expected_cleaning):
    quote = calculate_quote(listing(weekly_discount_pct=50, monthly_discount_pct=50), request(nights=nights))
    assert quote.cleaning_fee == expected_cleaning
    assert quote.discount == (quote.lodging_subtotal / 2).quantize(D("0.01"))


@pytest.mark.parametrize(
    "guests,expected_extra",
    [(1, D("0.00")), (2, D("0.00")), (4, D("120.00")), (5, D("150.00")), (8, D("150.00"))],
)
def test_extra_guest_cap_is_aggregate_per_night(guests, expected_extra):
    pricey = listing(extra_guest_fee=D("30"))
    quote = calculate_quote(pricey, request(nights=2, guests=guests))
    assert quote.extra_guest_fee == expected_extra


def test_extra_guests_are_outside_service_fee_but_inside_tax_base():
    without = calculate_quote(listing(), request(guests=2))
    with_extra = calculate_quote(listing(), request(guests=4))
    assert with_extra.extra_guest_fee == D("20.00")
    assert with_extra.service_fee == without.service_fee == D("21.30")
    assert with_extra.tax - without.tax == D("3.40")


def test_guest_count_is_not_limited_by_max_guests():
    quote = calculate_quote(listing(max_guests=2), request(guests=10))
    assert quote.extra_guest_fee == D("75.00")


def test_partner_grosses_up_lodging_and_drops_service_fee():
    web = calculate_quote(listing(), request(nights=1))
    partner = calculate_quote(listing(), request(nights=1, channel="partner"))
    assert web.lodging == D("100")
    assert web.service_fee == D("21.30")
    assert partner.lodging == D("112.00")
    assert partner.lodging != (D("100") / D("0.88")).quantize(D("0.01"))
    assert partner.service_fee == D("0.00")
    assert partner.discount == web.discount


def test_partner_gross_up_applies_after_discount():
    quote = calculate_quote(listing(nightly_rate=D("7"), cleaning_fee=D("0")), request(nights=1, channel="partner"))
    assert quote.lodging == D("7.84")
    quote = calculate_quote(listing(weekly_discount_pct=10), request(nights=7, channel="partner"))
    assert quote.discount == D("73.00")
    assert quote.lodging == D("735.84")


def test_web_service_fee_is_on_discounted_lodging_plus_cleaning():
    quote = calculate_quote(listing(weekly_discount_pct=10), request(nights=7))
    assert quote.lodging == D("657.00")
    assert quote.service_fee == D("100.39")


@pytest.mark.parametrize(
    "code,nights,expected",
    [
        ("SF", 1, D("21.00")),
        ("AUS", 1, D("17.00")),
        ("NYC", 1, D("24.13")),
        ("NYC", 29, D("80.13")),
        ("NYC", 30, D("0.00")),
        ("MIA", 1, D("20.80")),
    ],
)
def test_jurisdiction_tax_bases_and_rates(code, nights, expected):
    # lodging 90 + extra 10 = 100 always taxed; cleaning 50; service 10.
    tax = occupancy_tax(code, nights, D("90"), D("50"), D("10"), D("10"))
    assert tax == expected


def test_nyc_exemption_also_drops_per_night_fee():
    assert occupancy_tax("NYC", 30, D("0"), D("0"), D("0"), D("0")) == D("0.00")
    assert occupancy_tax("NYC", 29, D("0"), D("0"), D("0"), D("0")) == D("58.00")


def test_tax_cent_rounding_is_half_up():
    assert occupancy_tax("AUS", 1, D("12.50"), D("0"), D("0"), D("0")) == D("2.13")


def test_mia_taxes_rounded_service_fee():
    quote = calculate_quote(listing(jurisdiction="MIA"), request(nights=1))
    assert quote.service_fee == D("21.30")
    assert quote.tax == ((D("100") + D("50") + D("21.30")) * D("0.13")).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def test_total_sums_all_components():
    quote = calculate_quote(listing(jurisdiction="SF"), request(nights=2, guests=3, check_in=THURSDAY))
    assert quote.total == (
        quote.lodging + quote.cleaning_fee + quote.extra_guest_fee + quote.service_fee + quote.tax
    )


def test_requests_do_not_share_state():
    a = request(listing_id="sf-loft", nights=3, channel="web")
    b = request(listing_id="mia-villa", nights=10, channel="partner", guests=9, promo_code="VIP12PLUS")
    first = quote_to_dict(get_quote(a))
    other = quote_to_dict(get_quote(b))
    again = quote_to_dict(get_quote(a))
    assert first == again
    assert len(first["nightly_rates"]) == 3
    assert len(other["nightly_rates"]) == 10


def test_serialization_has_exact_fields_and_two_decimal_strings():
    data = quote_to_dict(get_quote(request(listing_id="nyc-studio", nights=2, guests=3)))
    assert list(data) == list(QUOTE_FIELDS)
    assert "summary" not in data
    assert data["nights"] == 2
    assert data["currency"] == "USD"
    money = [data[name] for name in QUOTE_FIELDS if name not in ("listing_id", "nights", "currency", "nightly_rates")]
    for value in money + data["nightly_rates"]:
        assert isinstance(value, str)
        whole, _, cents = value.partition(".")
        assert whole.isdigit() and len(cents) == 2 and cents.isdigit()


def test_unknown_listing_raises():
    with pytest.raises(ListingNotFound):
        get_listing("nope")
    with pytest.raises(ListingNotFound):
        get_quote(request(listing_id="nope"))
