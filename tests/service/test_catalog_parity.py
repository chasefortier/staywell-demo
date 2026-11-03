"""Field-by-field comparison of the copied catalog against the legacy reference data.

Only tests import staywell; quote_service itself must stay independent.
"""
from dataclasses import asdict
from decimal import Decimal

from quote_service import catalog, jurisdictions, promos
from staywell import jurisdictions as legacy_jurisdictions
from staywell import listings as legacy_listings
from staywell import promos as legacy_promos


def test_all_eight_listings_are_copied_exactly():
    assert list(catalog.LISTINGS) == list(legacy_listings.LISTINGS)
    assert len(catalog.LISTINGS) == 8
    for listing_id, legacy in legacy_listings.LISTINGS.items():
        assert asdict(catalog.LISTINGS[listing_id]) == asdict(legacy), listing_id


def test_catalog_money_and_multipliers_are_decimal():
    for listing in catalog.LISTINGS.values():
        for value in (listing.nightly_rate, listing.cleaning_fee, listing.extra_guest_fee):
            assert isinstance(value, Decimal), listing.id
        assert all(isinstance(m, Decimal) for m in listing.seasonal_multipliers.values()), listing.id
    for promo in promos.PROMOS.values():
        assert isinstance(promo.fixed, Decimal), promo.code
    for code, rule in jurisdictions.RULES.items():
        assert isinstance(rule.rate, Decimal) and isinstance(rule.per_night_fee, Decimal), code


def test_all_four_promos_are_copied_exactly():
    assert list(promos.PROMOS) == list(legacy_promos.PROMOS)
    for code, legacy in legacy_promos.PROMOS.items():
        assert asdict(promos.PROMOS[code]) == asdict(legacy), code


def test_all_four_jurisdiction_rules_are_copied_exactly():
    assert list(jurisdictions.RULES) == list(legacy_jurisdictions.RULES)
    for code, legacy in legacy_jurisdictions.RULES.items():
        rule = jurisdictions.RULES[code]
        assert {
            "rate": rule.rate,
            "taxes_cleaning": rule.taxes_cleaning,
            "taxes_service_fee": rule.taxes_service_fee,
            "exempt_after_nights": rule.exempt_after_nights,
            "per_night_fee": rule.per_night_fee,
        } == legacy, code
