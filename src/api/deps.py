"""FastAPI dependency providers — the wiring between repositories and services.

This is the ONLY module allowed to import the concrete `YFinance*Repository`/
`Postgres*Repository` classes; every service type-hints its repository
dependency as the `PriceRepository`/`CompanyRepository` Protocol. The Phase
4.8 Postgres cutover (production-roadmap.md §6) lives entirely here: if
`DATABASE_URL` is set, `get_price_repository`/`get_company_repository` build
Postgres-backed repositories instead of the yfinance-backed ones — no
service, router, or schema changes required, by design.

Singletons are done via `functools.lru_cache` on zero-arg (or
hashable-args-only) functions — FastAPI's documented pattern for
"construct once, reuse across requests" dependencies. `Config` (a pydantic
model, not hashable without extra config) is deliberately never passed as an
argument to an `lru_cache`d function — it's fetched with a plain call to
`get_config()` instead, which is itself cached.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import sessionmaker

from src.config import Config, load_config
from src.repositories.base import CompanyRepository, CorrelationRepository, PriceRepository
from src.repositories.postgres.company_repository import PostgresCompanyRepository
from src.repositories.postgres.correlation_repository import PostgresCorrelationRepository
from src.repositories.postgres.db import make_engine, make_session_factory
from src.repositories.postgres.price_repository import PostgresPriceRepository
from src.repositories.yfinance_company_repository import YFinanceCompanyRepository
from src.repositories.yfinance_price_repository import YFinancePriceRepository
from src.services.company_service import CompanyService
from src.services.correlation_service import CorrelationService
from src.services.graph_service import GraphService
from src.services.price_service import PriceService


@lru_cache
def get_config() -> Config:
    return load_config()


@lru_cache
def get_session_factory() -> sessionmaker | None:
    """`None` when DATABASE_URL isn't set — the one place the Postgres
    cutover is decided (Phase 4.8). One engine/session factory shared by both
    repositories below, not one each.
    """
    config = get_config()
    if not config.database_url:
        return None
    return make_session_factory(make_engine(config.database_url))


@lru_cache
def get_price_repository() -> PriceRepository:
    config = get_config()
    session_factory = get_session_factory()
    if session_factory is not None:
        return PostgresPriceRepository(
            session_factory, config.data_dir / "cache", cache_ttl_seconds=config.price_cache_ttl_seconds
        )
    return YFinancePriceRepository(config.data_dir / "cache", cache_ttl_seconds=config.price_cache_ttl_seconds)


@lru_cache
def get_company_repository() -> CompanyRepository:
    config = get_config()
    session_factory = get_session_factory()
    if session_factory is not None:
        return PostgresCompanyRepository(
            session_factory, config.data_dir / "cache", cache_ttl_seconds=config.price_cache_ttl_seconds
        )
    return YFinanceCompanyRepository(config.data_dir / "cache", cache_ttl_seconds=config.price_cache_ttl_seconds)


def get_price_service(price_repo: PriceRepository = Depends(get_price_repository)) -> PriceService:
    return PriceService(price_repo, get_config().lookback_days)


def get_company_service(company_repo: CompanyRepository = Depends(get_company_repository)) -> CompanyService:
    return CompanyService(company_repo)


@lru_cache
def get_correlation_repository() -> CorrelationRepository | None:
    """`None` when DATABASE_URL isn't set — CorrelationService then always
    computes live. When Postgres is wired, the graph endpoint serves stored
    snapshots (Track A Phase 1) written by `python -m src.cli compute-correlations`.
    """
    session_factory = get_session_factory()
    if session_factory is None:
        return None
    return PostgresCorrelationRepository(session_factory)


@lru_cache
def get_correlation_service(
    price_repo: PriceRepository = Depends(get_price_repository),
    company_repo: CompanyRepository = Depends(get_company_repository),
    correlation_repo: CorrelationRepository | None = Depends(get_correlation_repository),
) -> CorrelationService:
    # @lru_cache (not just a plain factory) matters here specifically:
    # CorrelationService holds an in-memory result cache as instance state,
    # which needs to survive across requests, not just across sub-dependency
    # construction.
    return CorrelationService(price_repo, company_repo, get_config(), correlation_repo=correlation_repo)


def get_graph_service(
    correlation_service: CorrelationService = Depends(get_correlation_service),
    company_repo: CompanyRepository = Depends(get_company_repository),
) -> GraphService:
    return GraphService(correlation_service, company_repo)
