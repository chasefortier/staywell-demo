"""Guest booking confirmation emails."""
from __future__ import annotations

import re

from staywell.services.pricing import get_quote

SUMMARY_PATTERN = re.compile(r"^(?P<nights>\d+) nights? x .* \| Total \$(?P<total>[\d,]+\.\d{2})$")


def build_confirmation_email(guest_name, request):
    quote = get_quote(request)
    match = SUMMARY_PATTERN.match(quote["summary"])
    if not match:
        return f"Hi {guest_name}, your StayWell booking is confirmed."
    nights = int(match.group("nights"))
    total = match.group("total")
    stay = "1-night stay" if nights == 1 else f"{nights}-night stay"
    return f"Hi {guest_name}, your {stay} is confirmed. Total charged: ${total}."
