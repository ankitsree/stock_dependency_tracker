import pandas as pd

from src.errors import TickerNotFoundError
from src.services.graph_service import GraphService


class _FakeCorrelationService:
    def __init__(self, rankings: dict, missing: set = frozenset()):
        self._rankings = rankings
        self._missing = missing
        self.calls = []
        self.prefetch_calls = []

    def prefetch_prices(self, anchors, force_refresh=False):
        self.prefetch_calls.append((tuple(anchors), force_refresh))
        return "PREFETCHED_PRICES"

    def rank_with_full_diagnostics(
        self, anchor, exclude_tickers=None, top_n=None, threshold=None, force_refresh=False, prefetched_prices=None
    ):
        self.calls.append((anchor, exclude_tickers, force_refresh, prefetched_prices))
        if anchor in self._missing:
            raise TickerNotFoundError(anchor)
        return _FakeResult(
            self._rankings.get(anchor, pd.DataFrame(columns=["ticker", "name", "sector", "correlation"]))
        )


class _FakeResult:
    def __init__(self, satellites):
        self.satellites = satellites


class _FakeCompanyRepository:
    def __init__(self):
        self.calls = []

    def get_market_data(self, tickers, force_refresh=False):
        self.calls.append(tuple(sorted(tickers)))
        return pd.DataFrame(columns=["ticker", "market_cap", "avg_volume"])


def _ranked(ticker="SAT1", correlation=0.8):
    return pd.DataFrame(
        [(ticker, f"{ticker} Co", "Semiconductors", correlation)], columns=["ticker", "name", "sector", "correlation"]
    )


def test_build_graph_composes_rankings_for_each_anchor():
    correlation_service = _FakeCorrelationService({"NVDA": _ranked("SAT1"), "TSM": _ranked("SAT2")})
    graph_service = GraphService(correlation_service, _FakeCompanyRepository())

    graph = graph_service.build_graph(["NVDA", "TSM"])

    assert graph.has_edge("NVDA", "SAT1")
    assert graph.has_edge("TSM", "SAT2")


def test_build_graph_excludes_all_anchors_from_each_others_candidate_pool():
    correlation_service = _FakeCorrelationService({"NVDA": _ranked("SAT1")})
    graph_service = GraphService(correlation_service, _FakeCompanyRepository())

    graph_service.build_graph(["NVDA", "TSM", "ASML"])

    anchor, exclude_tickers, _, _ = correlation_service.calls[0]
    assert anchor == "NVDA"
    assert exclude_tickers == {"NVDA", "TSM", "ASML"}


def test_build_graph_prefetches_prices_once_and_reuses_across_anchors():
    correlation_service = _FakeCorrelationService({"NVDA": _ranked("SAT1"), "TSM": _ranked("SAT2")})
    graph_service = GraphService(correlation_service, _FakeCompanyRepository())

    graph_service.build_graph(["NVDA", "TSM"])

    # One prefetch for the whole build, not one per anchor — this is the fix
    # for the redundant per-anchor Yahoo downloads.
    assert correlation_service.prefetch_calls == [(("NVDA", "TSM"), False)]
    assert all(call[3] == "PREFETCHED_PRICES" for call in correlation_service.calls)


def test_build_graph_skips_anchor_with_no_data_instead_of_failing():
    correlation_service = _FakeCorrelationService({"TSM": _ranked("SAT2")}, missing={"NVDA"})
    graph_service = GraphService(correlation_service, _FakeCompanyRepository())

    graph = graph_service.build_graph(["NVDA", "TSM"])

    assert "NVDA" not in graph.nodes
    assert graph.has_edge("TSM", "SAT2")


def test_build_graph_metadata_fetched_only_for_graphed_tickers():
    correlation_service = _FakeCorrelationService({"NVDA": _ranked("SAT1")})
    company_repo = _FakeCompanyRepository()
    graph_service = GraphService(correlation_service, company_repo)

    graph_service.build_graph(["NVDA"])

    assert company_repo.calls == [("NVDA", "SAT1")]


def test_build_graph_no_anchors_produce_empty_graph_without_metadata_call():
    company_repo = _FakeCompanyRepository()
    graph_service = GraphService(_FakeCorrelationService({}, missing={"NVDA"}), company_repo)

    graph = graph_service.build_graph(["NVDA"])

    assert graph.number_of_nodes() == 0
    assert company_repo.calls == []


def test_get_graph_json_returns_plain_dict():
    correlation_service = _FakeCorrelationService({"NVDA": _ranked("SAT1")})
    graph_service = GraphService(correlation_service, _FakeCompanyRepository())

    result = graph_service.get_graph_json(["NVDA"])

    assert isinstance(result, dict)
    assert result["nodes"] and result["edges"]


def test_get_relatedness_matrix_returns_dataframe():
    correlation_service = _FakeCorrelationService({"NVDA": _ranked("SHARED", 0.8), "TSM": _ranked("SHARED", 0.6)})
    graph_service = GraphService(correlation_service, _FakeCompanyRepository())

    matrix = graph_service.get_relatedness_matrix(["NVDA", "TSM"])

    assert matrix.loc["NVDA", "TSM"] == 0.6
