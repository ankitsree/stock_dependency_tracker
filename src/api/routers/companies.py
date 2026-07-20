from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.api import deps
from src.api.schemas.companies import CompanyListResponse
from src.domain.models import CompanyProfile
from src.services.company_service import CompanyService

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=CompanyListResponse)
def list_companies(
    include_market_data: bool = Query(default=False),
    force_refresh: bool = Query(default=False),
    company_service: CompanyService = Depends(deps.get_company_service),
) -> CompanyListResponse:
    companies = company_service.list_universe(include_market_data=include_market_data, force_refresh=force_refresh)
    return CompanyListResponse(companies=companies)


@router.get("/{ticker}", response_model=CompanyProfile)
def get_company(
    ticker: str,
    force_refresh: bool = Query(default=False),
    company_service: CompanyService = Depends(deps.get_company_service),
) -> CompanyProfile:
    return company_service.get_company_profile(ticker.upper(), force_refresh=force_refresh)
