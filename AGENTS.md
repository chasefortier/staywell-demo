# AGENTS.md

StayWell is a vacation-rental platform. This repo is the pricing slice of an 8-year-old Python monolith. Website checkout, the mobile app, host payouts and confirmation emails all depend on `staywell/services/pricing.py`. We are extracting that engine into a standalone FastAPI service that will back the partner API.

## Layout

| Path | What it is |
|---|---|
| `staywell/services/pricing.py` | Legacy quote engine (`QuoteCalculator.call()`). The behavior is the spec. |
| `staywell/jurisdictions.py` | Occupancy tax rules for SF, AUS, NYC, MIA |
| `staywell/listings.py`, `staywell/promos.py` | In-memory catalog standing in for the Django ORM |
| `staywell/services/host_payout.py` | Host payouts. Reads `QuoteCalculator._lodging_total` directly. |
| `staywell/services/booking_confirmation.py` | Confirmation emails. Regex-parses the quote `summary` string. |
| `tests/fixtures/golden_master.json` | 129 cases captured from legacy behavior. **The contract.** |
| `quote_service/` | The new FastAPI service (to be built) |
| `docs/quirks.md` | Every legacy quirk, documented (to be written) |

## Commands

```bash
python3 -m unittest discover -s tests -t . -v   # legacy unit tests (stdlib only)
python3 scripts/check_golden_master.py          # legacy engine vs golden master, must be 129/129
python3 scripts/demo_facts.py                   # rounding drift, quirk coverage, payout gap
scripts/serve.sh                                # start quote_service on 127.0.0.1:8080 (once it exists)
pytest tests/contract -q                        # replay the golden master over HTTP (once it exists)
```

## Hard rules

1. **Never modify `tests/fixtures/golden_master.json`, and never run `scripts/capture_golden_master.py`.** If a case looks wrong, document it in `docs/quirks.md` and stop. A hook enforces this.
2. **Preserve legacy behavior exactly, including quirks.** Cent for cent, on every field in the fixture.
3. **No silent bug fixes.** If something looks like a bug, especially anything that changes money charged to guests or paid to hosts, record it in `docs/quirks.md` with evidence and leave the behavior unchanged. A human decides, and the fix ships as its own reviewed change.
4. **Nightly prices use Python's built-in `round()`**, which rounds halves to even. Do not "fix" this to half-up. 25 of the 129 cases change if you do.
5. **Money is `Decimal`, never `float`.** Serialize money as strings with two decimal places, exactly as the fixture does.
6. **Do not change behavior in `staywell/services/pricing.py`.** It stays as the reference implementation until the migration is signed off.
7. **`quote_service/` must not import from `staywell`.** It is a standalone service with its own copy of the rules.
8. **One PR per milestone**, titled `[quote-service] M<n>: <summary>`, with the golden master result in the description.

## quote_service conventions

- Python 3.9+. Dependencies (FastAPI, uvicorn, pydantic, httpx, pytest) pinned in `requirements-service.txt`. The legacy `staywell` package stays standard-library only.
- `scripts/serve.sh` starts the service with one command on `127.0.0.1:8080` and writes logs to `logs/quote_service.log`. `logs/` is gitignored.
- `GET /healthz` returns `{"status": "ok"}`.
- `POST /v1/quotes` takes `listing_id`, `check_in` (YYYY-MM-DD), `nights`, `guests`, optional `promo_code`, and `channel` (`web` or `partner`). It returns exactly the fields in the fixture's `expected` objects. Unknown listing: 404. Invalid input: 422.
- Version the API under `/v1`. Partners will pin to it.

## Definition of done for any milestone

- Legacy unit tests pass, and `scripts/check_golden_master.py` reports 129/129.
- Every golden master case that the milestone covers passes over HTTP against a running service.
- `docs/quirks.md` is updated for every rule the milestone touched.
