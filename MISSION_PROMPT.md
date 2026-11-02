# Mission prompt

Paste everything below the line after running `/missions`.

---

Extract StayWell's pricing engine from the Python monolith into a standalone FastAPI service that will back our partner API. Read AGENTS.md first and follow its hard rules.

**Context.** `staywell/services/pricing.py` is an 8-year-old quote engine that nobody fully owns. Two of the three engineers who understand it are leaving. Two large partners will not sign until they can request quotes over a stable API. Website checkout, host payouts and confirmation emails depend on this code today, and two of those callers depend on its internals.

**Non-negotiable acceptance criteria**

1. Reproduce every case in `tests/fixtures/golden_master.json` exactly, cent for cent, through a pytest suite in `tests/contract/` that replays all 129 cases against the running HTTP service (`POST /v1/quotes`).
2. Preserve legacy behavior, including quirks. Where a quirk looks like a bug, do not fix it. Record it in `docs/quirks.md` with the file and line, what it does, which golden master cases exercise it, and whether it looks intentional.
3. Remove the summary-string coupling. The service returns structured fields. Add `staywell/adapters/quote_client.py`, and migrate `staywell/services/host_payout.py` and `staywell/services/booking_confirmation.py` to use it instead of `QuoteCalculator` internals and the regex. Host payout amounts and email contents must not change. Prove it with tests.
4. `scripts/serve.sh` starts the service with one command. Validators should start it, hit `/healthz`, run the contract suite, and read `logs/quote_service.log`.
5. `quote_service/` must not import from `staywell`.

**Milestones**

1. **Characterize.** Read the legacy code and the fixture. Write `docs/quirks.md` covering every rule. Scaffold `quote_service/`, `scripts/serve.sh`, `/healthz`, and the contract test harness, which may fail at this point.
2. **Core engine.** Nightly pricing: seasonal multipliers, the cap, the weekend uplift and half-even rounding. Cases without discounts, partners or extra guests pass.
3. **Discounts and fees.** Stay discounts, promo codes, cleaning fee rules, extra-guest fees, service fee.
4. **Taxes, partner logic and HTTP contract.** Jurisdiction rules, partner gross-up, error handling, versioned `/v1` contract. All 129 cases pass over HTTP.
5. **Caller migration.** The adapter, host payout and booking confirmation moved off the internals, with tests showing identical outputs.

Do not mark a milestone complete while any golden master case it covers fails. Open one PR per milestone.
