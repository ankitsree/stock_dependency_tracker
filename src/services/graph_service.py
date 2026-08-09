from __future__ import annotations

import logging

import networkx as nx
import pandas as pd

from src.errors import TickerNotFoundError
from src.graph.builder import build_multi_anchor_graph
from src.graph.queries import anchor_relatedness_matrix, graph_to_node_link_dict
from src.repositories.base import CompanyRepository
from src.services.correlation_service import CorrelationService

logger = logging.getLogger(__name__)


class GraphService:
    def __init__(self, correlation_service: CorrelationService, company_repo: CompanyRepository):
        self._correlation_service = correlation_service
        self._company_repo = company_repo

    def build_graph(
        self,
        anchors: list[str],
        top_n: int | None = None,
        threshold: float | None = None,
        force_refresh: bool = False,
    ) -> nx.Graph:
        # Fetched once for every anchor up front rather than letting each
        # anchor's own ranking call fetch it separately — see
        # CorrelationService.prefetch_prices for why that matters (it's the
        # difference between one Yahoo download and one per anchor).
        prefetched_prices = self._correlation_service.prefetch_prices(anchors, force_refresh=force_refresh)

        anchor_rankings: dict[str, pd.DataFrame] = {}
        for anchor in anchors:
            try:
                result = self._correlation_service.rank_with_full_diagnostics(
                    anchor,
                    exclude_tickers=set(anchors),
                    top_n=top_n,
                    threshold=threshold,
                    force_refresh=force_refresh,
                    prefetched_prices=prefetched_prices,
                )
            except TickerNotFoundError:
                logger.warning("Skipping anchor %s in graph build: no price data available", anchor)
                continue
            if not result.satellites.empty:
                anchor_rankings[anchor] = result.satellites

        # Only anchors that actually produced a ranking end up as graph
        # nodes (build_multi_anchor_graph only adds a node per
        # anchor_rankings entry) — fetching metadata for a requested-but-
        # unavailable anchor would be a wasted call for a ticker that never
        # appears in the output.
        satellite_tickers = {ticker for df in anchor_rankings.values() for ticker in df["ticker"]}
        metadata_tickers = sorted(set(anchor_rankings.keys()) | satellite_tickers)
        metadata = (
            self._company_repo.get_market_data(metadata_tickers, force_refresh=force_refresh)
            if metadata_tickers
            else pd.DataFrame(columns=["ticker", "market_cap", "avg_volume"])
        )
        return build_multi_anchor_graph(anchor_rankings, metadata)

    def get_graph_json(self, anchors: list[str], **kwargs) -> dict:
        return graph_to_node_link_dict(self.build_graph(anchors, **kwargs))

    def get_relatedness_matrix(self, anchors: list[str], **kwargs) -> pd.DataFrame:
        return anchor_relatedness_matrix(self.build_graph(anchors, **kwargs))
