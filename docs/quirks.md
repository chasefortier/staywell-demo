# Pricing quirks

This is the inventory of every pricing rule the standalone `quote_service` copies from the legacy engine. The behavior is preserved exactly, quirks included. Nothing listed here has been fixed. Any change to money charged to guests or paid to hosts must ship as its own reviewed change after a human decision.

Conventions:

- **Source** cites the original legacy code at baseline `7afa2d2`. That code remains the reference implementation.
- **Golden cases** lists IDs from the frozen 129-case golden master whose requests exercise the rule. "None" means no frozen case reaches the branch. Those branches are covered only by the focused tests in `tests/service/test_engine_rules.py`, which use test-local listings and requests.
- **Intent** is one of: *intentional* (a deliberate business rule), *suspicious* (looks like a bug, preserved anyway), or *unresolved* (the intent cannot be determined from the code).
- The service copy lives in `quote_service/pricing.py`, `quote_service/jurisdictions.py`, `quote_service/catalog.py` and `quote_service/promos.py`. All 129 frozen cases are compared directly against the service engine in `tests/service/test_engine_golden.py`.

## 1. Nightly rates

### 1.1 Seasonal multiplier is capped at 1.5x, then the weekend uplift goes on top

- **Source:** `staywell/services/pricing.py:19-21`, `staywell/services/pricing.py:43-49`
- **Behavior and order:** For each occupied night, look up the multiplier for that night's calendar month (default `Decimal("1")`), cap it with `min(multiplier, 1.5)`, and only then multiply by `1.15` if the night starts on a Friday or Saturday (`weekday()` 4 or 5). The weekend uplift is not re-capped, so a capped weekend night is priced at 1.725x. Example: mia-condo in December has a 1.7 multiplier, which is capped to 1.5, so a Friday night is 205 x 1.5 x 1.15 = 353.625, rounded to 354.
- **Golden cases:** Capped month on a weekend night: gm-003, gm-004, gm-005, gm-006, gm-037, gm-060, gm-111, gm-114.
- **Intent:** Suspicious. The comment at line 43 states the order on purpose, but the result exceeds the stated 1.5x cap. The README calls it "a bug, may be intentional". Preserved unchanged.

### 1.2 The multiplier is chosen per night by that night's month

- **Source:** `staywell/services/pricing.py:44-46`
- **Behavior and order:** Night `i` is `check_in + i days`. A stay that crosses a month boundary prices each night with its own month's multiplier. Months without an entry use 1.
- **Golden cases:** 47 cases use at least one seasonal month, for example gm-003 through gm-013 and gm-017 through gm-020. The fixture does not specifically target a month boundary inside one stay.
- **Intent:** Intentional.

### 1.3 Weekend means nights that start on Friday or Saturday

- **Source:** `staywell/services/pricing.py:21`, `staywell/services/pricing.py:48-49`
- **Behavior and order:** The uplift applies to the nights of Friday and Saturday (the date of the night, not the check-out date). Sunday nights are not uplifted.
- **Golden cases:** 100 of 129 cases include at least one Friday or Saturday night, for example gm-003, gm-007 and gm-024.
- **Intent:** Intentional.

### 1.4 Whole-dollar nights with built-in `round()` (half to even)

- **Source:** `staywell/services/pricing.py:50-52`
- **Behavior and order:** Each night is `Decimal(round(nightly_rate * multiplier))`. Python's built-in `round()` on a `Decimal` returns an `int` and rounds ties to the even neighbor, so 264.5 becomes 264, 218.5 becomes 218 and 412.5 becomes 412. The subtotal is the sum of the already-rounded nights. Nightly rates are serialized as two-decimal strings such as `"218.00"`.
- **Golden cases:** Switching to half-up changes 25 cases: gm-005, gm-009, gm-019, gm-020, gm-024, gm-025, gm-026, gm-036, gm-037, gm-057, gm-060, gm-061, gm-065, gm-071, gm-076, gm-077, gm-083, gm-086, gm-090, gm-091, gm-092, gm-097, gm-100, gm-108, gm-116 (from `scripts/demo_facts.py`). Landmarks: gm-024 (264.5 to 264), gm-025 (218.5 to 218), gm-005 (412.5 to 412).
- **Intent:** Unresolved. This is most likely an accident of using `round()` rather than a decided rounding policy, but it is what guests are charged today. Do not change it to half-up.

## 2. Discounts

### 2.1 Weekly discount at 7+ nights, monthly at 28+ nights

- **Source:** `staywell/services/pricing.py:25-26`, `staywell/services/pricing.py:55-59`
- **Behavior and order:** `nights >= 28` uses the listing's monthly percentage. Otherwise `nights >= 7` uses the weekly percentage. Otherwise the stay percentage is 0. Monthly replaces weekly; they never add.
- **Golden cases:** Threshold edges: 6 nights gm-083, gm-105, gm-106, gm-127; 7 nights gm-018, gm-063, gm-069, gm-094, gm-097, gm-102, gm-107, gm-110, gm-113, gm-121; 27 nights gm-013; 28 nights gm-012, gm-031, gm-051, gm-058, gm-065, gm-068, gm-071, gm-100, gm-117. Weekly applies in 37 cases and monthly in 22.
- **Intent:** Intentional.

### 2.2 Percentage discounts do not stack: the larger percentage wins

- **Source:** `staywell/services/pricing.py:60-62`
- **Behavior and order:** `pct = max(stay_pct, promo.pct)`. The discount is `lodging_subtotal * pct / 100`, rounded half-up to cents. Percentages are whole numbers. Because the subtotal is whole dollars, this product never lands on a half cent.
- **Golden cases:** Equal percentages (tie): gm-007, gm-033. Promo percentage wins: gm-008, gm-009, gm-018, gm-028, gm-052, gm-057, gm-077, gm-084, gm-092, gm-094, gm-113, gm-116. Stay percentage wins: gm-037, gm-051, gm-058, gm-061, gm-065, gm-117, gm-118.
- **Intent:** Intentional (undocumented business rule).

### 2.3 A fixed promo amount stacks after the percentage

- **Source:** `staywell/services/pricing.py:62-64`
- **Behavior and order:** The fixed amount is added after the percentage discount has been rounded to cents. A promo with `fixed == Decimal("0")` adds nothing because zero is falsy.
- **Golden cases:** Fixed amount on top of a percentage: gm-009, gm-026, gm-028, gm-030, gm-031, gm-035, gm-049, gm-050, gm-051, gm-055, gm-058, gm-064, gm-076, gm-077, gm-080, gm-104, gm-106, gm-108, gm-112, gm-113, gm-117, gm-125. Fixed amount alone: gm-010, gm-011, gm-045, gm-046, gm-047, gm-070, gm-093.
- **Intent:** Intentional.

### 2.4 The discount is clamped to the lodging subtotal

- **Source:** `staywell/services/pricing.py:65-66`
- **Behavior and order:** `discount = min(discount, lodging_subtotal)`, then `lodging = lodging_subtotal - discount`. Lodging can reach zero but never goes negative. The clamp affects only lodging; cleaning, extra-guest fees and taxes still apply.
- **Golden cases:** None. With the current catalog (cheapest night $145) and promos (largest fixed amount $40) the clamp is unreachable. Covered by `test_fixed_promo_discount_is_clamped_to_subtotal` and `test_clamped_partner_quote_grosses_up_zero_lodging`.
- **Intent:** Intentional (defensive).

### 2.5 Promo codes are exact, case-sensitive, and silently ignored when unknown

- **Source:** `staywell/services/pricing.py:60`, `staywell/promos.py:9-14`
- **Behavior and order:** `PROMOS.get(code) if code else None`. `None` and the empty string mean no promo. Unknown codes and codes with different case or surrounding whitespace (for example `summer10` or `"SUMMER10 "`) are ignored without an error and price exactly like a request without a promo. Promos have no date, listing, channel or minimum-stay restrictions. The four codes are SUMMER10 (10%), FALL15 (15%), WELCOME25 ($25 fixed) and VIP12PLUS (12% plus $40).
- **Golden cases:** Each valid code appears (SUMMER10 in gm-007, FALL15 in gm-008, VIP12PLUS in gm-009, WELCOME25 in gm-010, among others). Unknown, empty and differently-cased codes: none. Covered by `test_unknown_empty_or_differently_cased_promo_is_ignored`.
- **Intent:** Unresolved. Silently ignoring a mistyped code may surprise guests, but it is current behavior.

## 3. Fees

### 3.1 Cleaning is never discounted and is waived at 28+ nights

- **Source:** `staywell/services/pricing.py:68-69`
- **Behavior and order:** Cleaning is the listing's flat fee, or zero when `nights >= 28`. It is computed after the discount and is never reduced by it. The waiver uses the monthly threshold, not the 30-night NYC threshold.
- **Golden cases:** 27 nights pays cleaning: gm-013. 28 nights waives it: gm-012. 22 cases are 28+ nights in total.
- **Intent:** Intentional.

### 3.2 Extra-guest fee: aggregate $75 per-night cap, multiplied by nights

- **Source:** `staywell/services/pricing.py:22`, `staywell/services/pricing.py:71-74`
- **Behavior and order:** `min(max(0, guests - included_guests) * extra_guest_fee, 75) * nights`. The cap applies to the total for all extra guests on a night, not to each guest. The fee is not discounted.
- **Golden cases:** Cap reached: gm-014, gm-015, gm-016, gm-027, gm-029, gm-031, gm-032, gm-039, gm-045, gm-052, gm-059, gm-068, gm-074, gm-075, gm-082, gm-084, gm-098, gm-103, gm-109, gm-112, gm-115, gm-120, gm-121, gm-125. 63 cases have at least one extra guest.
- **Intent:** Intentional.

### 3.3 Guest count is not checked against `max_guests`

- **Source:** `staywell/services/pricing.py:72` (`max_guests` from `staywell/listings.py:13-118` is never read)
- **Behavior and order:** Requests above a listing's capacity are priced normally, with the extra-guest cap applying.
- **Golden cases:** None. Covered by `test_guest_count_is_not_limited_by_max_guests`.
- **Intent:** Unresolved. The service does not add a capacity limit.

### 3.4 Extra-guest fees are outside the service-fee base and are not grossed up for partners

- **Source:** `staywell/services/pricing.py:71`, `staywell/services/pricing.py:76-81`
- **Behavior and order:** The web service fee base is lodging plus cleaning only. The partner gross-up multiplies lodging only. Extra-guest fees are added to the total unchanged. They are still part of every tax base (see 5.1).
- **Golden cases:** Any case with extra guests, for example gm-014 (web) and gm-017 (partner).
- **Intent:** Intentional (a subtle base rule).

## 4. Channel

### 4.1 Partner lodging is grossed up by 12%, with no service fee

- **Source:** `staywell/services/pricing.py:24`, `staywell/services/pricing.py:76-79`
- **Behavior and order:** For `channel == "partner"`, discounted lodging is multiplied by `1.12` and rounded half-up to cents. This is multiplication by 1.12, not division by 0.88. The service fee is `Decimal("0.00")`. The gross-up happens after the discount and before tax, so occupancy tax is charged on the grossed-up lodging. The response `discount` is the pre-gross-up discount, so for partner quotes `lodging_subtotal - discount` does not equal `lodging`.
- **Golden cases:** 33 partner cases, including gm-002 (the same stay as web gm-001), gm-017, gm-021, gm-023 and gm-125.
- **Intent:** Intentional for the guest price. See 7.1 for the host-payout side effect.

### 4.2 Web service fee is 14.2% of discounted lodging plus cleaning

- **Source:** `staywell/services/pricing.py:23`, `staywell/services/pricing.py:80-81`
- **Behavior and order:** `(lodging + cleaning) * 0.142`, rounded half-up to cents. Lodging is already discounted. Extra-guest fees are excluded. Any channel value other than `"partner"` is treated as web by the engine; the HTTP API is responsible for accepting only `web` and `partner`.
- **Golden cases:** 96 web cases, for example gm-001.
- **Intent:** Intentional.

## 5. Occupancy tax

### 5.1 Tax base always starts with lodging plus extra-guest fees

- **Source:** `staywell/services/pricing.py:84-87`, `staywell/jurisdictions.py:43-53`
- **Behavior and order:** Tax is computed after lodging (grossed up for partners), cleaning (possibly waived) and the rounded service fee. The base is `lodging + extra_guests`, plus cleaning and service fee when the rule says so. `base * rate` is rounded half-up to cents once, then the per-night fee is added.
- **Golden cases:** All 129 cases.
- **Intent:** Intentional. The rules are invented for the demo and are not real tax law (`staywell/jurisdictions.py:3`).

### 5.2 SF: 14%, includes cleaning

- **Source:** `staywell/jurisdictions.py:12-18`
- **Behavior and order:** Base is lodging, extra guests and cleaning. No service fee, no exemption, no per-night fee.
- **Golden cases:** 38 cases, for example gm-001, gm-002, gm-007, gm-012, gm-024.
- **Intent:** Intentional.

### 5.3 AUS: 17%, excludes cleaning and service fee

- **Source:** `staywell/jurisdictions.py:19-25`
- **Behavior and order:** Base is lodging and extra guests only.
- **Golden cases:** 28 cases, for example gm-003, gm-009, gm-011, gm-014, gm-025.
- **Intent:** Intentional.

### 5.4 NYC: 14.75% plus $2 per night, both exempt at 30+ nights

- **Source:** `staywell/jurisdictions.py:26-32`, `staywell/jurisdictions.py:45-46`, `staywell/jurisdictions.py:52-53`
- **Behavior and order:** Base is lodging, extra guests and cleaning. The percentage is rounded to cents first, then `2.00 * nights` is added. At `nights >= 30` the whole tax, including the per-night fee, is `0.00`. The field is named `exempt_after_nights`, but the comparison is inclusive, so exactly 30 nights is exempt.
- **Golden cases:** 29 nights taxed: gm-019. 30 nights exempt: gm-020, gm-103. All exempt stays: gm-020, gm-021, gm-041, gm-103, gm-118. 34 NYC cases in total.
- **Intent:** Intentional rule. The inclusive comparison against a field named "after" is unresolved; the fixture freezes the inclusive behavior.

### 5.5 MIA: 13%, includes cleaning and the rounded service fee

- **Source:** `staywell/jurisdictions.py:33-39`, `staywell/jurisdictions.py:50-51`
- **Behavior and order:** Base is lodging, extra guests, cleaning and the service fee after it has been rounded to cents. Partner quotes have a zero service fee, so nothing is added for them.
- **Golden cases:** Web gm-022 and partner gm-023 for the same stay. 29 MIA cases in total.
- **Intent:** Intentional.

## 6. Totals and serialization

### 6.1 Total is the plain sum, then everything is rounded half-up to cents

- **Source:** `staywell/services/pricing.py:16`, `staywell/services/pricing.py:29-30`, `staywell/services/pricing.py:89-103`
- **Behavior and order:** `total = lodging + cleaning + extra + service_fee + tax`. Every component is already at whole cents, so the final `_money()` (half-up to `0.01`) on each output field never changes a value; it only fixes the representation to two decimal places. Currency is always `"USD"`.
- **Golden cases:** All 129 cases.
- **Intent:** Intentional.

### 6.2 The frozen fields exclude the legacy summary string

- **Source:** `staywell/services/pricing.py:104-114`, `scripts/_golden.py:28-48`
- **Behavior and order:** The legacy quote also has a `summary` string (average nightly lodging, cleaning, service, tax and total with thousands separators). The fixture serializes only the 12 structured fields, with each nightly rate and money value as a two-decimal string and `nights` as an integer. The service has no summary.
- **Golden cases:** All 129 cases (field shape).
- **Intent:** Intentional. The summary's consumer is documented with the caller migration.

### 6.3 Unknown listing

- **Source:** `staywell/listings.py:123-131`, `staywell/services/pricing.py:117-118`
- **Behavior and order:** An unknown `listing_id` raises `ListingNotFound` before any pricing.
- **Golden cases:** None (every frozen request uses a catalog listing). Covered by `test_unknown_listing_raises`.
- **Intent:** Intentional.

## 7. Known suspicious behavior outside the quote

### 7.1 Partner hosts are paid on grossed-up lodging

- **Source:** `staywell/services/host_payout.py:17-21`
- **Behavior and order:** Host payout is 97% of `QuoteCalculator._lodging_total` plus cleaning, rounded half-up to cents. For partner bookings `_lodging_total` already includes the 12% commission gross-up from 4.1, so a partner host earns more than a web host for the same stay: $582.19 versus $528.65 on the sample stay, a $53.54 gap.
- **Golden cases:** The sample stay is the request in gm-001 (web) and gm-002 (partner). Payouts are not frozen fields, so no case checks them directly.
- **Intent:** Suspicious (likely a bug that overpays partner hosts). Preserved unchanged. A human decides whether to fix it as its own change.
