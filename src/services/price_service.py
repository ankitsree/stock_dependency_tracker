from __future__ import annotations

from src.domain.models import PricePoint
from src.errors import TickerNotFoundError
from src.repositories.base import PriceRepository


class PriceService:
    def __init__(self, price_repo: PriceRepository, default_lookback_days: int):
        self._price_repo = price_repo
        self.default_lookback_days = default_lookback_days

    def get_price_history(
        self,
        ticker: str,
        lookback_days: int | None = None,
        force_refresh: bool = False,
    ) -> list[PricePoint]:
        lookback_days = lookback_days if lookback_days is not None else self.default_lookback_days
        prices = self._price_repo.get_price_history([ticker], lookback_days, force_refresh=force_refresh)
        if ticker not in prices.columns:
            raise TickerNotFoundError(ticker)
        series = prices[ticker].dropna()
        return [PricePoint(date=index.date(), adjusted_close=float(value)) for index, value in series.items()]
