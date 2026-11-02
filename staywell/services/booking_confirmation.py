"""Guest booking confirmation emails."""
from __future__ import annotations

from staywell.adapters import quote_client


def build_confirmation_email(guest_name, request):
    quote = quote_client.fetch_quote(request)
    return (
        f"Hi {guest_name}, your {quote['nights']}-night stay is confirmed."
        f" Total charged: ${quote['total']:,.2f}."
    )
