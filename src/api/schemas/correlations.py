from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from src.domain.models import RankedSatellite


class CorrelationResponse(BaseModel):
    anchor: str
    satellites: list[RankedSatellite]
    generated_at: dt.datetime
    cache_hit: bool
