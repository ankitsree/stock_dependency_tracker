from __future__ import annotations

import networkx as nx
import pandas as pd


def top_satellites_for_anchor(graph: nx.Graph, anchor: str, n: int = 10) -> list[tuple[str, float]]:
    """Satellites connected to `anchor`, sorted by |correlation| descending."""
    edges = [(sat, graph[anchor][sat]["weight"]) for sat in graph.neighbors(anchor)]
    edges.sort(key=lambda pair: abs(pair[1]), reverse=True)
    return edges[:n]


def shared_satellites(graph: nx.Graph) -> dict[str, list[str]]:
    """Satellites connected to more than one anchor, mapped to those anchors.

    This is where cross-cutting themes show up: a satellite under both NVDA
    and TSM implies a link between those two anchors' ecosystems.
    """
    anchors = [n for n, d in graph.nodes(data=True) if d["kind"] == "anchor"]
    result = {}
    for node, data in graph.nodes(data=True):
        if data["kind"] != "satellite":
            continue
        connected = [a for a in anchors if graph.has_edge(node, a)]
        if len(connected) > 1:
            result[node] = connected
    return result


def strongest_cross_link(graph: nx.Graph) -> tuple[str, str, str, float] | None:
    """The pair of anchors with the strongest indirect link via a shared satellite.

    "Strength" of an (anchor_a, anchor_b) pair through satellite S is the
    smaller of the two edge weights (a chain is only as strong as its
    weakest link). Returns (anchor_a, anchor_b, satellite, strength), or None
    if no satellite is shared by more than one anchor.
    """
    best = None
    for satellite, anchors in shared_satellites(graph).items():
        for i in range(len(anchors)):
            for j in range(i + 1, len(anchors)):
                a, b = anchors[i], anchors[j]
                strength = min(abs(graph[a][satellite]["weight"]), abs(graph[b][satellite]["weight"]))
                if best is None or strength > best[3]:
                    best = (a, b, satellite, strength)
    return best


def anchor_relatedness_matrix(graph: nx.Graph) -> pd.DataFrame:
    """Roadmap Phase 4's "correlation of correlations" view: how related is
    each pair of anchors, inferred purely from the satellites they share
    (no anchor-anchor price correlation is computed directly).

    For every satellite shared by two or more anchors, each pair of those
    anchors gets one "link strength" sample — the weaker of their two edge
    weights to that satellite (same reasoning as `strongest_cross_link`: a
    chain is only as strong as its weakest link). A pair's final score is the
    mean of all such samples across every satellite they share, so an anchor
    pair linked through many satellites scores higher than one linked
    through a single coincidental overlap. Anchor pairs with no shared
    satellite score 0.0.

    Returns a square DataFrame indexed and columned by anchor ticker
    (symmetric, zero diagonal).
    """
    anchors = [n for n, d in graph.nodes(data=True) if d["kind"] == "anchor"]
    pair_strengths: dict[tuple[str, str], list[float]] = {}
    for satellite, connected in shared_satellites(graph).items():
        for i in range(len(connected)):
            for j in range(i + 1, len(connected)):
                low, high = sorted((connected[i], connected[j]))
                pair = (low, high)
                strength = min(abs(graph[low][satellite]["weight"]), abs(graph[high][satellite]["weight"]))
                pair_strengths.setdefault(pair, []).append(strength)

    matrix = pd.DataFrame(0.0, index=anchors, columns=anchors)
    for (a, b), strengths in pair_strengths.items():
        score = sum(strengths) / len(strengths)
        matrix.loc[a, b] = score
        matrix.loc[b, a] = score
    return matrix


_EDGE_METRIC_COLUMNS = (
    "stability",
    "pearson_correlation",
    "partial_correlation",
    "sector_relative_correlation",
    "best_lag",
    "best_lag_correlation",
    "regime_break",
    "regime_drift",
)


def graph_to_node_link_dict(graph: nx.Graph) -> dict:
    """Serialize a dependency graph to plain nodes/edges lists — JSON-ready,
    with no networkx types left in it. This is the canonical shape the API's
    /graph endpoint (and any future frontend) consumes; field sets mirror
    src.domain.models.GraphNode/GraphEdge and builder.OPTIONAL_EDGE_COLUMNS.
    """
    nodes = [
        {
            "ticker": ticker,
            "kind": data.get("kind"),
            "name": data.get("name", ticker),
            "sector": data.get("sector", ""),
            "market_cap": data.get("market_cap"),
            "avg_volume": data.get("avg_volume"),
        }
        for ticker, data in graph.nodes(data=True)
    ]

    edges = []
    for u, v, data in graph.edges(data=True):
        anchor, satellite = (u, v) if graph.nodes[u]["kind"] == "anchor" else (v, u)
        edge = {"anchor": anchor, "satellite": satellite, "weight": data["weight"]}
        edge.update({col: data.get(col) for col in _EDGE_METRIC_COLUMNS})
        edges.append(edge)

    return {"nodes": nodes, "edges": edges}
