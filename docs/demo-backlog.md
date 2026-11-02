# Demo backlog

Tickets and automation prompts used in the demo. Create them in Linear (or Jira) in the interview org before the panel.

## Ticket for the delegation beat (Act 5)

**Title:** Add X-Request-ID to quote responses

**Description:**
Partners need to correlate quotes with their own logs. For every `POST /v1/quotes` response, return an `X-Request-ID` header. If the request includes `X-Request-ID`, echo it back; otherwise generate a UUID4. Log the ID with each request in `logs/quote_service.log`. Add contract tests for both cases. Do not change any response body field. Follow AGENTS.md.

Assign it to Droid after the Mission's milestone 4 PR is merged, and keep the resulting PR open for the demo.

## Automation for the shadow quote check (Act 5)

**Type:** Scheduled (nightly)

**Prompt:**
Start the quote service with `scripts/serve.sh`. Take 25 cases at random from `tests/fixtures/golden_master.json` (stand-ins for sampled production quotes) and send each one to `POST /v1/quotes`. Compare every money field with the expected value, cent for cent. If anything differs, open a Linear ticket titled "Quote mismatch: <case id>" with the request, the expected and actual fields, and the latest lines of `logs/quote_service.log`. If everything matches, post a one-line summary and do not open a ticket. Never modify the fixture.

To get a ticket for the demo, run it once against a branch where the nightly rounding is switched to half-up. That produces mismatches in the rounding cases.

## Questions to seed during Act 1

- "Explain how a quote is calculated in this repo, step by step, and list anything that would surprise a new engineer."
- "Which callers depend on pricing internals, and what would break if the summary format changed?"
