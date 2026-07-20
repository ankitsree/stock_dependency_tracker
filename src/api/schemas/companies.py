from __future__ import annotations

from pydantic import BaseModel

from src.domain.models import CompanyProfile


class CompanyListResponse(BaseModel):
    companies: list[CompanyProfile]
