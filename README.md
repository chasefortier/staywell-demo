# StayWell demo: quote engine extraction

A small, runnable stand-in for StayWell's Python monolith, built for a Factory demo. The legacy quote engine has undocumented rules, two callers with hidden coupling, and almost no tests. A 129-case golden master gives a Factory Mission an objective pass or fail gate while it extracts the engine into a FastAPI service.

The legacy code uses only the Python standard library (3.9+). The FastAPI service does not exist yet. Building it is the Mission.

> The tax rules in `staywell/jurisdictions.py` are invented for the demo and are not real tax law.

## Quickstart

```bash
scripts/check                                 # unit tests and all 129 golden master cases
python3 -m unittest discover -s tests -t . -v   # unit tests, including payout regressions
python3 scripts/check_golden_master.py          # 129/129 against the legacy engine
python3 scripts/demo_facts.py                   # the numbers quoted in the demo
```

## Verified demo facts

Produced by `scripts/demo_facts.py`. Rerun it after any change and before you present.

| Fact | Value |
|---|---|
| Golden master cases | 129 |
| Cases that change if nightly rounding becomes half-up | **25 of 129** |
| Sample stay host payout, web | $528.65 |
| Same stay, partner booking | $528.65 |
| Partner payout gap on the sample stay | **$0.00** |
| Existing unit tests | 6 |

## The seven legacy quirks

Numbered comments in `staywell/services/pricing.py` mark each one.

| # | Rule | Looks like |
|---|---|---|
| 1 | Seasonal multiplier capped at 1.5x, then the Fri/Sat 1.15x uplift applies on top of the cap | A bug, may be intentional |
| 2 | Percentage discounts don't stack: the larger of stay discount and promo wins. A fixed promo amount stacks after | Undocumented business rule |
| 3 | Cleaning fee is never discounted, and is waived for stays of 28+ nights | Easy to miss |
| 4 | Extra-guest fee capped at $75 per night and left out of the service-fee base | A subtle base rule |
| 5 | Partner bookings skip the service fee and gross lodging up by 12% commission before tax | Exactly what the partner API needs |
| 6 | NYC exempts stays of 30+ nights and adds $2 per night; MIA taxes the service fee; AUS doesn't tax cleaning | Edge cases thin tests miss |
| 7 | Each night is rounded to whole dollars with built-in `round()`, which rounds halves to even | A rewrite trap |

**Partner payout correction (CHA-5):** The original `HostPayout` used `QuoteCalculator._lodging_total`, including the partner's commission gross-up, and overpaid the sample partner host by $53.54. The partner payout now uses lodging subtotal minus discount, plus cleaning, before applying the 97% host share. Web payouts and all legacy quote rules remain unchanged. See `docs/quirks.md` for the preserved gross-up rule and regression evidence.

## Layout

```
staywell/
  models.py, listings.py, promos.py, jurisdictions.py
  services/pricing.py               legacy engine
  services/host_payout.py           reads pricing internals
  services/booking_confirmation.py  regex-parses the summary string
tests/
  test_pricing.py                   3 happy-path tests
  fixtures/golden_master.json       the contract
scripts/
  capture_golden_master.py          refuses to overwrite without --force
  check_golden_master.py            legacy engine vs the contract
  demo_facts.py                     numbers for the presenter
.factory/hooks.json                 blocks agent edits to the golden master
.github/workflows/ci.yml            legacy checks, fixture guard, contract suite
AGENTS.md                           conventions and hard rules for Droids
MISSION_PROMPT.md                   paste after /missions
docs/demo-backlog.md                tickets and automation prompts for the demo
```
