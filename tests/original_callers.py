"""Test-only frozen copies of the original host payout and confirmation email.

These reproduce the caller code at baseline 7afa2d2, before the callers moved to
the quote service adapter:

- ``staywell/services/host_payout.py:17-21`` read the private
  ``QuoteCalculator._lodging_total`` after ``call()``.
- ``staywell/services/booking_confirmation.py:8-19`` regex-parsed the legacy
  quote ``summary`` string.

They are oracles for parity tests only. Production code must not use them.
"""
import re
from decimal import ROUND_HALF_UP, Decimal

from staywell.listings import get_listing
from staywell.services.pricing import QuoteCalculator, get_quote

ORIGINAL_HOST_SHARE = Decimal("0.97")
CENT = Decimal("0.01")
ORIGINAL_SUMMARY_PATTERN = re.compile(r"^(?P<nights>\d+) nights? x .* \| Total \$(?P<total>[\d,]+\.\d{2})$")

# Names cycle across the frozen cases so interpolation is checked with
# punctuation, accents, braces, surrounding spaces and non-Latin scripts.
GUEST_NAMES = (
    "Avery",
    "María José",
    "O'Brien-Smith",
    "Dr. Lee, Jr.",
    "Zoë",
    "{guest_name}",
    "  Sam  ",
    "李雷",
)


def guest_name_for(index):
    return GUEST_NAMES[index % len(GUEST_NAMES)]


def original_host_payout(request):
    calculator = QuoteCalculator(get_listing(request.listing_id), request)
    quote = calculator.call()
    base = calculator._lodging_total + quote["cleaning_fee"]
    return (base * ORIGINAL_HOST_SHARE).quantize(CENT, rounding=ROUND_HALF_UP)


def original_confirmation_email(guest_name, request):
    quote = get_quote(request)
    match = ORIGINAL_SUMMARY_PATTERN.match(quote["summary"])
    if not match:
        return f"Hi {guest_name}, your StayWell booking is confirmed."
    nights = int(match.group("nights"))
    total = match.group("total")
    stay = "1-night stay" if nights == 1 else f"{nights}-night stay"
    return f"Hi {guest_name}, your {stay} is confirmed. Total charged: ${total}."


def original_summary_matches(request):
    return ORIGINAL_SUMMARY_PATTERN.match(get_quote(request)["summary"]) is not None
