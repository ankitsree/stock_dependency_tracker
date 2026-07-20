from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from src.domain.models import PricePoint


class PriceHistoryResponse(BaseModel):
    ticker: str
    lookback_days: int
    points: list[PricePoint]
    generated_at: dt.datetime
