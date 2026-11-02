"""Characterization of host payouts and confirmation emails over every frozen request.

The production callers are compared with the frozen original behavior in
``tests/original_callers.py``. The structured formulas below are what the
callers compute from a structured quote, and are checked against the original
private-state and summary-parsing behavior for all 129 requests.
"""
import unittest
from decimal import ROUND_HALF_UP, Decimal

from scripts._golden import load_cases, request_from_dict, serialize_quote
from staywell.services.booking_confirmation import build_confirmation_email
from staywell.services.host_payout import HostPayout
from staywell.services.pricing import get_quote
from tests.original_callers import (
    guest_name_for,
    original_confirmation_email,
    original_host_payout,
    original_summary_matches,
)

CASES = load_cases()
CASES_BY_ID = {case["id"]: case for case in CASES}


def structured_payout(expected):
    base = Decimal(expected["lodging"]) + Decimal(expected["cleaning_fee"])
    return (base * Decimal("0.97")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def structured_email(guest_name, expected):
    return (
        f"Hi {guest_name}, your {expected['nights']}-night stay is confirmed."
        f" Total charged: ${Decimal(expected['total']):,.2f}."
    )


class CallerCharacterizationTests(unittest.TestCase):
    def test_every_frozen_request_is_characterized(self):
        self.assertEqual(len(CASES), 129)
        self.assertEqual(len(CASES_BY_ID), 129)

    def test_host_payout_matches_original_for_every_frozen_request(self):
        for case in CASES:
            with self.subTest(case=case["id"]):
                request = request_from_dict(case["request"])
                payout = HostPayout(request).compute()
                self.assertIs(type(payout), Decimal)
                self.assertEqual(payout.as_tuple().exponent, -2)
                self.assertEqual(payout, original_host_payout(request))

    def test_confirmation_email_matches_original_for_every_frozen_request(self):
        for index, case in enumerate(CASES):
            with self.subTest(case=case["id"]):
                request = request_from_dict(case["request"])
                name = guest_name_for(index)
                email = build_confirmation_email(name, request)
                self.assertIs(type(email), str)
                self.assertEqual(email, original_confirmation_email(name, request))

    def test_original_summary_parse_never_falls_back(self):
        for case in CASES:
            with self.subTest(case=case["id"]):
                self.assertTrue(original_summary_matches(request_from_dict(case["request"])))

    def test_original_payout_equals_structured_lodging_plus_cleaning(self):
        for case in CASES:
            with self.subTest(case=case["id"]):
                request = request_from_dict(case["request"])
                self.assertEqual(serialize_quote(get_quote(request)), case["expected"])
                self.assertEqual(original_host_payout(request), structured_payout(case["expected"]))

    def test_original_email_equals_structured_nights_and_total(self):
        for index, case in enumerate(CASES):
            with self.subTest(case=case["id"]):
                request = request_from_dict(case["request"])
                name = guest_name_for(index)
                self.assertEqual(original_confirmation_email(name, request), structured_email(name, case["expected"]))

    def test_sample_payouts_preserve_partner_gap(self):
        web = HostPayout(request_from_dict(CASES_BY_ID["gm-001"]["request"])).compute()
        partner = HostPayout(request_from_dict(CASES_BY_ID["gm-002"]["request"])).compute()
        self.assertEqual(web, Decimal("528.65"))
        self.assertEqual(partner, Decimal("582.19"))
        self.assertEqual(partner - web, Decimal("53.54"))

    def test_partner_payout_uses_grossed_up_lodging_not_subtotal_minus_discount(self):
        expected = CASES_BY_ID["gm-002"]["expected"]
        reconstructed = Decimal(expected["lodging_subtotal"]) - Decimal(expected["discount"])
        self.assertNotEqual(reconstructed, Decimal(expected["lodging"]))
        self.assertEqual(structured_payout(expected), Decimal("582.19"))

    def test_sample_emails(self):
        cases = {
            "gm-001": "Hi Avery, your 2-night stay is confirmed. Total charged: $698.69.",
            "gm-011": "Hi Avery, your 1-night stay is confirmed. Total charged: $294.79.",
            "gm-003": "Hi Avery, your 4-night stay is confirmed. Total charged: $1,336.52.",
            "gm-012": "Hi Avery, your 28-night stay is confirmed. Total charged: $8,623.25.",
        }
        for case_id, expected in cases.items():
            with self.subTest(case=case_id):
                request = request_from_dict(CASES_BY_ID[case_id]["request"])
                self.assertEqual(build_confirmation_email("Avery", request), expected)

    def test_one_night_and_five_digit_totals_are_covered(self):
        one_night = [case["id"] for case in CASES if case["request"]["nights"] == 1]
        five_digit = [case["id"] for case in CASES if Decimal(case["expected"]["total"]) >= 10000]
        self.assertEqual(len(one_night), 8)
        self.assertEqual(len(five_digit), 14)
        for case_id in one_night + five_digit:
            with self.subTest(case=case_id):
                case = CASES_BY_ID[case_id]
                email = build_confirmation_email("Avery", request_from_dict(case["request"]))
                total = Decimal(case["expected"]["total"])
                if case["request"]["nights"] == 1:
                    self.assertIn("your 1-night stay is confirmed.", email)
                if total >= 10000:
                    self.assertRegex(email, r"Total charged: \$\d{2},\d{3}\.\d{2}\.$")


if __name__ == "__main__":
    unittest.main()
