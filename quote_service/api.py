"""HTTP boundary for the quote service.

Partners pin to ``/v1``; its request and response shapes must not change.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator

from quote_service.catalog import ListingNotFound
from quote_service.models import QuoteRequest
from quote_service.pricing import get_quote
from quote_service.serialization import quote_to_dict

ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


class QuoteRequestBody(BaseModel):
    # Strict mode rejects booleans, numeric strings and floats for the counts.
    model_config = ConfigDict(strict=True)

    listing_id: StrictStr
    check_in: date
    nights: StrictInt = Field(gt=0)
    guests: StrictInt = Field(gt=0)
    promo_code: Optional[StrictStr] = None
    channel: Literal["web", "partner"] = "web"

    @field_validator("check_in", mode="before")
    @classmethod
    def _check_in_is_yyyy_mm_dd(cls, value):
        if not isinstance(value, str) or not ISO_DATE.fullmatch(value):
            raise ValueError("check_in must be a YYYY-MM-DD string")
        return date.fromisoformat(value)

    def to_domain(self) -> QuoteRequest:
        return QuoteRequest(
            listing_id=self.listing_id,
            check_in=self.check_in,
            nights=self.nights,
            guests=self.guests,
            promo_code=self.promo_code,
            channel=self.channel,
        )


app = FastAPI(title="StayWell quote service", version="1")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/v1/quotes")
def create_quote(body: QuoteRequestBody):
    try:
        quote = get_quote(body.to_domain())
    except ListingNotFound:
        raise HTTPException(status_code=404, detail=f"Unknown listing: {body.listing_id}") from None
    return JSONResponse(quote_to_dict(quote))
