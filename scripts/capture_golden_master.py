"""Capture the golden master from the legacy quote engine.

The fixture is the contract for the quote service extraction. Regenerating it
rewrites that contract, so this refuses to run unless --force is given.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, timedelta

from _golden import FIXTURE, request_from_dict, serialize_quote

from staywell.listings import LISTINGS
from staywell.services.pricing import get_quote

TOTAL_CASES = 129
SEED = 20190412

# Hand-picked cases that pin down each legacy rule before random coverage.
EDGE_CASES = [
    # weekday baseline and the sample stay used in tests
    {"listing_id": "sf-loft", "check_in": "2026-03-10", "nights": 2, "guests": 2},
    {"listing_id": "sf-loft", "check_in": "2026-03-10", "nights": 2, "guests": 2, "channel": "partner"},
    # seasonal cap, then weekend uplift on top
    {"listing_id": "aus-ranch", "check_in": "2027-03-11", "nights": 4, "guests": 4},
    {"listing_id": "mia-condo", "check_in": "2026-12-17", "nights": 4, "guests": 2},
    {"listing_id": "nyc-studio", "check_in": "2026-12-18", "nights": 3, "guests": 1},
    {"listing_id": "mia-villa", "check_in": "2026-12-25", "nights": 3, "guests": 6},
    # discounts do not stack; fixed promo stacks after
    {"listing_id": "sf-victorian", "check_in": "2026-07-06", "nights": 8, "guests": 4, "promo_code": "SUMMER10"},
    {"listing_id": "sf-victorian", "check_in": "2026-07-06", "nights": 8, "guests": 4, "promo_code": "FALL15"},
    {"listing_id": "aus-bungalow", "check_in": "2026-10-05", "nights": 10, "guests": 2, "promo_code": "VIP12PLUS"},
    {"listing_id": "nyc-brownstone", "check_in": "2026-11-02", "nights": 2, "guests": 4, "promo_code": "WELCOME25"},
    {"listing_id": "aus-ranch", "check_in": "2026-05-04", "nights": 1, "guests": 4, "promo_code": "WELCOME25"},
    # cleaning waived on monthly stays
    {"listing_id": "sf-loft", "check_in": "2026-08-01", "nights": 28, "guests": 2},
    {"listing_id": "sf-loft", "check_in": "2026-08-01", "nights": 27, "guests": 2},
    # extra guest fee capped per night
    {"listing_id": "aus-ranch", "check_in": "2026-06-08", "nights": 3, "guests": 10},
    {"listing_id": "mia-villa", "check_in": "2026-04-13", "nights": 5, "guests": 12},
    {"listing_id": "nyc-studio", "check_in": "2026-04-13", "nights": 2, "guests": 3},
    # partner gross-up
    {"listing_id": "nyc-brownstone", "check_in": "2026-12-04", "nights": 4, "guests": 6, "channel": "partner"},
    {"listing_id": "mia-condo", "check_in": "2027-02-12", "nights": 7, "guests": 3, "channel": "partner", "promo_code": "SUMMER10"},
    # jurisdiction rules: NYC exemption at 30 nights, MIA taxes the service fee
    {"listing_id": "nyc-studio", "check_in": "2026-09-01", "nights": 29, "guests": 1},
    {"listing_id": "nyc-studio", "check_in": "2026-09-01", "nights": 30, "guests": 1},
    {"listing_id": "nyc-brownstone", "check_in": "2026-09-01", "nights": 31, "guests": 5, "channel": "partner"},
    {"listing_id": "mia-condo", "check_in": "2026-05-11", "nights": 3, "guests": 2},
    {"listing_id": "mia-condo", "check_in": "2026-05-11", "nights": 3, "guests": 2, "channel": "partner"},
    # half-even rounding on a weekend night (230 * 1.15 = 264.5)
    {"listing_id": "sf-loft", "check_in": "2026-03-13", "nights": 2, "guests": 2},
    {"listing_id": "aus-bungalow", "check_in": "2026-04-17", "nights": 2, "guests": 2},
]

NIGHT_CHOICES = [1, 2, 2, 3, 3, 4, 5, 6, 7, 8, 10, 14, 21, 28, 30, 31]
PROMO_CHOICES = [None, None, None, None, "SUMMER10", "FALL15", "WELCOME25", "VIP12PLUS"]


def random_cases(rng, count):
    start = date(2026, 1, 1)
    listing_ids = sorted(LISTINGS)
    cases = []
    while len(cases) < count:
        listing = LISTINGS[rng.choice(listing_ids)]
        case = {
            "listing_id": listing.id,
            "check_in": (start + timedelta(days=rng.randrange(0, 540))).isoformat(),
            "nights": rng.choice(NIGHT_CHOICES),
            "guests": rng.randint(1, listing.max_guests),
        }
        promo = rng.choice(PROMO_CHOICES)
        if promo:
            case["promo_code"] = promo
        if rng.random() < 0.3:
            case["channel"] = "partner"
        cases.append(case)
    return cases


def build_cases():
    rng = random.Random(SEED)
    requests = EDGE_CASES + random_cases(rng, TOTAL_CASES - len(EDGE_CASES))
    cases = []
    for i, raw in enumerate(requests, start=1):
        req = {"promo_code": None, "channel": "web", **raw}
        quote = get_quote(request_from_dict(req))
        cases.append({"id": f"gm-{i:03d}", "request": req, "expected": serialize_quote(quote)})
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="overwrite the existing contract")
    args = parser.parse_args()
    if FIXTURE.exists() and not args.force:
        sys.exit(f"{FIXTURE} already exists. It is the extraction contract; refusing to overwrite.")
    cases = build_cases()
    payload = {
        "description": "Golden master captured from staywell.services.pricing. Do not edit by hand.",
        "money_format": "decimal strings, 2 places, USD",
        "case_count": len(cases),
        "cases": cases,
    }
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {len(cases)} cases to {FIXTURE}")


if __name__ == "__main__":
    main()
