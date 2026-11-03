import unittest
from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal
from unittest.mock import patch

from scripts._golden import load_cases, request_from_dict
from staywell.models import Promo
from staywell.promos import PROMOS
from staywell.services.host_payout import HostPayout
from tests.test_pricing import SAMPLE_STAY


class HostPayoutTests(unittest.TestCase):
    def test_partner_sample_payout_matches_web(self):
        partner = replace(SAMPLE_STAY, channel="partner")
        web_payout = HostPayout(SAMPLE_STAY).compute()

        self.assertEqual(web_payout, Decimal("528.65"))
        self.assertEqual(HostPayout(partner).compute(), web_payout)

    def test_payout_base_for_each_golden_stay_on_both_channels(self):
        for case in load_cases():
            quote = case["expected"]
            expected = (
                (
                    Decimal(quote["lodging_subtotal"])
                    - Decimal(quote["discount"])
                    + Decimal(quote["cleaning_fee"])
                )
                * Decimal("0.97")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            request = request_from_dict(case["request"])
            for channel in ("web", "partner"):
                with self.subTest(case=case["id"], channel=channel):
                    payout = HostPayout(replace(request, channel=channel)).compute()
                    self.assertEqual(payout, expected)

    def test_fully_discounted_partner_lodging_preserves_cleaning_rules(self):
        with patch.dict(PROMOS, {"FREE": Promo(code="FREE", fixed=Decimal("10000"))}):
            for nights, expected in ((2, Decimal("82.45")), (28, Decimal("0.00"))):
                with self.subTest(nights=nights):
                    request = replace(
                        SAMPLE_STAY, channel="partner", promo_code="FREE", nights=nights
                    )
                    self.assertEqual(HostPayout(request).compute(), expected)


if __name__ == "__main__":
    unittest.main()
