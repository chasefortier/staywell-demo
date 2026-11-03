# StayWell demo: quote engine extraction

A small, runnable stand-in for StayWell's Python monolith, built for a Factory demo. The legacy quote engine has undocumented rules, two callers with hidden coupling, and almost no tests. A 129-case golden master gives a Factory Mission an objective pass or fail gate while it extracts the engine into a FastAPI service.

The legacy code uses only the Python standard library (3.9+). The standalone FastAPI quote service lives in `quote_service/` and reproduces the legacy engine cent for cent. See [The quote service](#the-quote-service) below.

> The tax rules in `staywell/jurisdictions.py` are invented for the demo and are not real tax law.

## Quickstart

The legacy checks need only Python 3.9+ and no installed packages:

```bash
python3 -m unittest discover -s tests -t . -v   # legacy unit tests, stdlib only, no network
python3 scripts/check_golden_master.py          # 129/129 against the legacy engine
python3 scripts/demo_facts.py                   # the numbers quoted in the demo
```

## The quote service

`quote_service/` is a standalone FastAPI service that will back the partner API. It has its own copy of the listings, promotions, jurisdiction tax rules and pricing logic, and it never imports `staywell`. A test (`tests/service/test_service_independence.py`) enforces that. The legacy engine in `staywell/services/pricing.py` is unchanged and remains the reference implementation.

```
HTTP request -> quote_service/api.py (validation) -> quote_service/pricing.py -> quote_service/serialization.py
```

| Module | Role |
|---|---|
| `quote_service/api.py` | FastAPI app: `/healthz`, `POST /v1/quotes`, request validation, 404 for unknown listings |
| `quote_service/models.py` | Request and quote types |
| `quote_service/catalog.py`, `quote_service/promos.py` | Service-owned copies of the listing and promo data |
| `quote_service/jurisdictions.py` | Occupancy tax rules for SF, AUS, NYC and MIA |
| `quote_service/pricing.py` | Pure `Decimal` pricing engine, same calculation order and rounding as the legacy engine |
| `quote_service/serialization.py` | Explicit 12-field JSON shape with two-decimal money strings |

Every legacy rule and quirk the service copies, including the suspicious ones, is documented in [`docs/quirks.md`](docs/quirks.md) with its original source line and the golden master cases that exercise it. None of them were fixed.

### Setup

Python 3.9 or newer. The service dependencies are pinned in `requirements-service.txt` and go into a repository virtual environment, so the legacy package stays standard-library only.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-service.txt
```

### Run

```bash
scripts/serve.sh
```

This runs uvicorn in the foreground on `127.0.0.1:8080` (loopback only) using `.venv/bin/python` when it exists, otherwise `python3`. Stop it with Ctrl+C. Server output is appended to `logs/quote_service.log`, not the terminal, so follow it from another shell with `tail -f logs/quote_service.log`. `logs/` is gitignored.

Check that it is up:

```bash
curl http://127.0.0.1:8080/healthz
# {"status":"ok"}
```

### Request a quote

The API is versioned under `/v1`, and partners pin to it.

```bash
curl -X POST http://127.0.0.1:8080/v1/quotes \
  -H 'Content-Type: application/json' \
  -d '{"listing_id": "sf-loft", "check_in": "2026-03-10", "nights": 2, "guests": 2, "promo_code": null, "channel": "web"}'
```

```json
{"listing_id":"sf-loft","nights":2,"currency":"USD","nightly_rates":["230.00","230.00"],"lodging_subtotal":"460.00","discount":"0.00","lodging":"460.00","extra_guest_fee":"0.00","cleaning_fee":"85.00","service_fee":"77.39","tax":"76.30","total":"698.69"}
```

Request fields:

| Field | Type | Notes |
|---|---|---|
| `listing_id` | string | Required. Unknown listings return 404. |
| `check_in` | string | Required, `YYYY-MM-DD`. |
| `nights` | integer | Required, greater than 0. |
| `guests` | integer | Required, greater than 0. |
| `promo_code` | string or null | Optional, defaults to `null`. Matching is exact and case-sensitive; unknown codes mean no promo. |
| `channel` | `"web"` or `"partner"` | Optional, defaults to `"web"`. |

The response has exactly the 12 fields shown above, the same fields as the golden master's expected quotes. Money values and nightly rates are strings with two decimal places, computed as `Decimal`, never `float`. There is no `summary` field. Missing fields, wrong JSON types (including booleans or floats for counts), malformed dates, counts below 1, unknown channels and malformed JSON return 422. The service adds no capacity, future-date or maximum-stay limits that the legacy engine does not have.

### Test

With the service running from `scripts/serve.sh`:

```bash
.venv/bin/python -m pytest tests -q              # everything: legacy, service engine and HTTP contract tests
.venv/bin/python -m pytest tests/contract -q     # only the real-HTTP suite, including all 129 golden master cases
.venv/bin/python -m compileall -q quote_service staywell tests   # syntax check
```

`tests/service/` tests the engine directly, including all 129 golden master cases and focused rule tests for branches the fixture does not reach. `tests/contract/` sends real HTTP requests to the running service: all 129 golden master cases compared field for field, plus health, 404, 422, defaults and request-isolation checks. The contract suite never starts a server itself and fails with a clear message if none is reachable. Set `STAYWELL_QUOTE_SERVICE_URL` to point it somewhere other than `http://127.0.0.1:8080`.

Neither directory has an `__init__.py`, so plain `python3 -m unittest discover` skips them and stays offline and dependency-free.

### CI

`.github/workflows/ci.yml` runs three jobs:

- `legacy`: stdlib unit tests and the legacy golden master check on Python 3.9, with no packages installed.
- `fixture-guard`: on pull requests, fails if the golden master fixture differs from the base branch.
- `quote-service-contract`: installs `requirements-service.txt` on Python 3.9, starts `scripts/serve.sh`, waits for `/healthz`, runs `pytest tests -q` (including the 129-case HTTP replay) and the syntax check, then prints the service log.

### Pull requests

One pull request per milestone, titled `[quote-service] M<n>: <summary>`, with the legacy and HTTP golden master results in the description.

## Verified demo facts

Produced by `scripts/demo_facts.py`. Rerun it after any change and before you present.

| Fact | Value |
|---|---|
| Golden master cases | 129 |
| Cases that change if nightly rounding becomes half-up | **25 of 129** |
| Sample stay host payout, web | $528.65 |
| Same stay, partner booking | $582.19 |
| Partner host overpaid on the sample stay | **$53.54** |
| Existing unit tests | 3 |

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

**Latent bug (not commented anywhere):** `HostPayout` computes 97% of `QuoteCalculator._lodging_total` plus cleaning. For partner bookings that lodging figure already includes the 12% commission gross-up, so partner hosts are paid more than web hosts for the same stay. A good Mission flags this in `docs/quirks.md` and does not fix it.

## Layout

```
quote_service/                      standalone FastAPI quote service (no staywell imports)
staywell/
  models.py, listings.py, promos.py, jurisdictions.py
  services/pricing.py               legacy engine
  services/host_payout.py           reads pricing internals
  services/booking_confirmation.py  regex-parses the summary string
tests/
  test_pricing.py                   3 happy-path tests
  service/                          pytest: service engine, catalog parity, independence
  contract/                         pytest: real-HTTP contract suite against a running service
  fixtures/golden_master.json       the contract
scripts/
  capture_golden_master.py          refuses to overwrite without --force
  check_golden_master.py            legacy engine vs the contract
  demo_facts.py                     numbers for the presenter
  serve.sh                          starts quote_service on 127.0.0.1:8080
docs/quirks.md                      every legacy rule and quirk the service copies
requirements-service.txt            pinned service dependencies
.factory/hooks.json                 blocks agent edits to the golden master
.github/workflows/ci.yml            legacy checks, fixture guard, contract suite
AGENTS.md                           conventions and hard rules for Droids
MISSION_PROMPT.md                   paste after /missions
docs/demo-backlog.md                tickets and automation prompts for the demo
```
