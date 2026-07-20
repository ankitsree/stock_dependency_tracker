from __future__ import annotations

import networkx as nx
import pandas as pd

# Optional per-satellite columns that, when present on `ranked_satellites`,
# get carried onto the edge as extra metadata (roadmap Phase 4: "richer edge
# metadata"). Kept optional/generic the same way `stability` was in Phase 2,
# so Phase 1-3 callers whose ranked tables lack these columns are unaffected.
OPTIONAL_EDGE_COLUMNS = {
    "stability": float,
    "pearson_correlation": float,
    "partial_correlation": float,
    "sector_relative_correlation": float,
    "best_lag": int,
    "best_lag_correlation": float,
    "regime_break": bool,
    "regime_drift": float,
}


def build_dependency_graph(
    anchor: str,
    ranked_satellites: pd.DataFrame,
    metadata: pd.DataFrame | None = None,
) -> nx.Graph:
    """Build a star graph: one anchor hub node, connected to its ranked satellites.

    Edge weight is the Pearson correlation; if `ranked_satellites` has a
    `stability` column (see analysis.ranking.attach_stability) it's carried
    onto the edge too. `metadata` (ticker -> market_cap/avg_volume) is
    optional so this still works for the Phase 1 pipeline, which doesn't
    fetch it.
    """
    graph = nx.Graph()
    graph.add_node(anchor, kind="anchor", name=anchor, sector="Anchor", **_lookup_metadata(metadata, anchor))

    present_columns = [col for col in OPTIONAL_EDGE_COLUMNS if col in ranked_satellites.columns]
    for _, row in ranked_satellites.iterrows():
        ticker = row["ticker"]
        graph.add_node(
            ticker,
            kind="satellite",
            name=row["name"],
            sector=row["sector"],
            **_lookup_metadata(metadata, ticker),
        )

        edge_attrs = {"weight": float(row["correlation"])}
        for col in present_columns:
            if pd.notna(row[col]):
                edge_attrs[col] = OPTIONAL_EDGE_COLUMNS[col](row[col])
        graph.add_edge(anchor, ticker, **edge_attrs)

    return graph


def build_multi_anchor_graph(
    anchor_rankings: dict[str, pd.DataFrame],
    metadata: pd.DataFrame | None = None,
) -> nx.Graph:
    """Compose per-anchor star graphs into one combined graph.

    A satellite correlated with more than one anchor keeps a single node but
    gains an edge to each anchor it's connected to — this is what surfaces
    cross-cutting themes between anchors (roadmap Component 4).
    """
    graph = nx.Graph()
    for anchor, ranked in anchor_rankings.items():
        graph = nx.compose(graph, build_dependency_graph(anchor, ranked, metadata))
    return graph


def _lookup_metadata(metadata: pd.DataFrame | None, ticker: str) -> dict:
    if metadata is None or ticker not in metadata["ticker"].values:
        return {}
    row = metadata.loc[metadata["ticker"] == ticker].iloc[0]
    attrs = {}
    if pd.notna(row.get("market_cap")):
        attrs["market_cap"] = float(row["market_cap"])
    if pd.notna(row.get("avg_volume")):
        attrs["avg_volume"] = float(row["avg_volume"])
    return attrs
