# Pricing quirks: partner payout (CHA-5)

## Partner commission gross-up is a quote rule, not host earnings

`staywell/services/pricing.py:76-82` applies a 12% gross-up to discounted
lodging for partner quotes, rounds it to cents with `ROUND_HALF_UP`, skips
the service fee, and stores the grossed-up lodging in `_lodging_total`.
Taxes are then calculated on the legacy jurisdiction-specific bases.
This looks intentional for partner guest pricing. **Do not change it.**

The unchanged golden master exercises this rule in 33 partner cases:
gm-002, gm-017, gm-018, gm-021, gm-023, gm-026, gm-029, gm-032, gm-040,
gm-043, gm-045, gm-047, gm-054, gm-059, gm-062, gm-063, gm-069, gm-070,
gm-075, gm-079, gm-083, gm-087, gm-102, gm-104, gm-106, gm-107, gm-109,
gm-111, gm-112, gm-115, gm-116, gm-122 and gm-125.

## Payout coupling and the explicitly requested partner-only correction

Before CHA-5, `HostPayout.compute()` used `_lodging_total` plus cleaning for
both channels. For the sample stay (`sf-loft`, 2026-03-10, two nights, two
guests; partner quote case gm-002):

| Amount | Web | Partner |
|---|---|---|
| Discounted lodging before commission | $460.00 | $460.00 |
| Guest quote lodging | $460.00 | $515.20 |
| Cleaning | $85.00 | $85.00 |
| Original host payout (97% of quoted lodging plus cleaning) | $528.65 | $582.19 |

Paying hosts on the partner commission caused the $53.54 overpayment. The
sample regression test failed with `Decimal('582.19') != Decimal('528.65')`
before the payout change.

CHA-5 explicitly requests a separate, reviewed correction to the partner
payout path. That path now uses the quote's structured `lodging_subtotal`
minus `discount`, adds `cleaning_fee`, and applies the existing 97% share
and cent rounding. It does not reverse the rounded gross-up or change the
legacy quote engine. Both sample payouts are now $528.65.

Web payouts retain their existing calculation. Stay/promo discount
selection and capping (`pricing.py:54-66`), undiscounted cleaning and its
28-night waiver (`pricing.py:68-69`), and exclusion of extra-guest fees,
service fees and taxes from host earnings are unchanged. Nightly half-even
rounding is also unchanged.

`tests/test_host_payout.py` checks the sample, all 129 fixture stays on
both channels, and fully discounted lodging with and without cleaning.
The golden master remains the contract for guest quotes; it is not
regenerated or edited for this payout correction.
