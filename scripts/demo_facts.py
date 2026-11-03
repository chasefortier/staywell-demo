"""Print the numbers the demo relies on, computed from the code.

Run this before presenting so every figure you quote is current.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from _golden import load_cases, request_from_dict, serialize_quote

from staywell import listings
from staywell.services import pricing
from staywell.services.host_payout import HostPayout
from staywell.services.pricing import EXTRA_GUEST_NIGHTLY_CAP, SEASONAL_CAP, WEEKEND_DAYS


def half_up(value):
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def rounding_drift(cases):
    pricing.round = half_up
    try:
        return [c["id"] for c in cases if serialize_quote(pricing.get_quote(request_from_dict(c["request"]))) != c["expected"]]
    finally:
        del pricing.round


def quirk_coverage(cases):
    from datetime import timedelta

    counts = {k: 0 for k in ("1 seasonal cap + weekend", "2 discount stacking", "3 cleaning waived 28+",
                             "4 extra-guest cap", "5 partner gross-up", "6 NYC 30+ / MIA service tax")}
    for c in cases:
        r = request_from_dict(c["request"])
        listing = listings.get_listing(r.listing_id)
        nights = [r.check_in + timedelta(days=i) for i in range(r.nights)]
        if any(listing.seasonal_multipliers.get(n.month, 1) > SEASONAL_CAP or
               (listing.seasonal_multipliers.get(n.month, 1) >= SEASONAL_CAP and n.weekday() in WEEKEND_DAYS) for n in nights):
            counts["1 seasonal cap + weekend"] += 1
        stay = r.nights >= 7 and (listing.weekly_discount_pct or listing.monthly_discount_pct)
        if r.promo_code and (stay or r.promo_code in ("WELCOME25", "VIP12PLUS")):
            counts["2 discount stacking"] += 1
        if r.nights >= 28:
            counts["3 cleaning waived 28+"] += 1
        if (r.guests - listing.included_guests) * listing.extra_guest_fee > EXTRA_GUEST_NIGHTLY_CAP:
            counts["4 extra-guest cap"] += 1
        if r.channel == "partner":
            counts["5 partner gross-up"] += 1
        if (listing.jurisdiction == "NYC" and r.nights >= 30) or listing.jurisdiction == "MIA":
            counts["6 NYC 30+ / MIA service tax"] += 1
    return counts


def payout_gap():
    from tests.test_pricing import SAMPLE_STAY
    from dataclasses import replace

    web = HostPayout(SAMPLE_STAY).compute()
    partner = HostPayout(replace(SAMPLE_STAY, channel="partner")).compute()
    return web, partner


def main():
    cases = load_cases()
    drift = rounding_drift(cases)
    print(f"Golden master cases: {len(cases)}")
    print(f"Quirk 7, rounding: {len(drift)} of {len(cases)} cases change if nights use half-up rounding")
    print(f"  affected: {', '.join(drift)}")
    print("Quirk coverage (cases exercising each rule):")
    for name, n in quirk_coverage(cases).items():
        print(f"  {name}: {n}")
    web, partner = payout_gap()
    print(f"Sample stay payout: web host ${web}, partner host ${partner}, gap ${partner - web}")


if __name__ == "__main__":
    main()
