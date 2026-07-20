import pandas as pd

from src.graph.builder import build_dependency_graph, build_multi_anchor_graph
from src.graph.queries import (
    anchor_relatedness_matrix,
    graph_to_node_link_dict,
    shared_satellites,
    strongest_cross_link,
    top_satellites_for_anchor,
)


def _ranked():
    return pd.DataFrame(
        [
            ("SAT1", "Satellite One", "Semiconductors", 0.85),
            ("SAT2", "Satellite Two", "Semiconductors", -0.7),
        ],
        columns=["ticker", "name", "sector", "correlation"],
    )


def _ranked_with_stability():
    ranked = _ranked()
    ranked["stability"] = [0.9, 0.5]
    return ranked


def _metadata():
    return pd.DataFrame(
        [
            ("SAT1", 1_000_000_000, 500_000),
            ("SAT2", 2_000_000_000, 750_000),
        ],
        columns=["ticker", "market_cap", "avg_volume"],
    )


def test_graph_has_anchor_and_satellite_nodes():
    graph = build_dependency_graph("NVDA", _ranked())
    assert graph.number_of_nodes() == 3
    assert graph.nodes["NVDA"]["kind"] == "anchor"
    assert graph.nodes["SAT1"]["kind"] == "satellite"
    assert graph.nodes["SAT2"]["kind"] == "satellite"


def test_graph_edges_carry_correlation_weight():
    graph = build_dependency_graph("NVDA", _ranked())
    assert graph.number_of_edges() == 2
    assert graph["NVDA"]["SAT1"]["weight"] == 0.85
    assert graph["NVDA"]["SAT2"]["weight"] == -0.7


def test_satellite_node_metadata():
    graph = build_dependency_graph("NVDA", _ranked())
    assert graph.nodes["SAT1"]["name"] == "Satellite One"
    assert graph.nodes["SAT1"]["sector"] == "Semiconductors"


def test_edge_carries_stability_when_present():
    graph = build_dependency_graph("NVDA", _ranked_with_stability())
    assert graph["NVDA"]["SAT1"]["stability"] == 0.9
    assert graph["NVDA"]["SAT2"]["stability"] == 0.5


def test_edge_has_no_stability_key_when_absent():
    graph = build_dependency_graph("NVDA", _ranked())
    assert "stability" not in graph["NVDA"]["SAT1"]


def test_node_market_cap_and_volume_attached_from_metadata():
    graph = build_dependency_graph("NVDA", _ranked(), metadata=_metadata())
    assert graph.nodes["SAT1"]["market_cap"] == 1_000_000_000
    assert graph.nodes["SAT2"]["avg_volume"] == 750_000


def test_node_metadata_absent_ticker_gets_no_extra_attrs():
    graph = build_dependency_graph("NVDA", _ranked(), metadata=_metadata())
    assert "market_cap" not in graph.nodes["NVDA"]


def test_multi_anchor_graph_merges_shared_satellite():
    ranked_a = pd.DataFrame(
        [("SHARED", "Shared Co", "Semiconductors", 0.8)],
        columns=["ticker", "name", "sector", "correlation"],
    )
    ranked_b = pd.DataFrame(
        [("SHARED", "Shared Co", "Semiconductors", 0.6)],
        columns=["ticker", "name", "sector", "correlation"],
    )
    graph = build_multi_anchor_graph({"NVDA": ranked_a, "TSM": ranked_b})

    assert graph.number_of_nodes() == 3  # NVDA, TSM, SHARED (not duplicated)
    assert graph["NVDA"]["SHARED"]["weight"] == 0.8
    assert graph["TSM"]["SHARED"]["weight"] == 0.6


def test_top_satellites_for_anchor_sorted_by_abs_weight():
    graph = build_dependency_graph("NVDA", _ranked())
    top = top_satellites_for_anchor(graph, "NVDA", n=1)
    assert top == [("SAT1", 0.85)]


def test_shared_satellites_finds_multi_anchor_overlap():
    ranked_a = pd.DataFrame(
        [("SHARED", "Shared Co", "Semiconductors", 0.8)],
        columns=["ticker", "name", "sector", "correlation"],
    )
    ranked_b = pd.DataFrame(
        [("SHARED", "Shared Co", "Semiconductors", 0.6)],
        columns=["ticker", "name", "sector", "correlation"],
    )
    graph = build_multi_anchor_graph({"NVDA": ranked_a, "TSM": ranked_b})
    shared = shared_satellites(graph)
    assert shared == {"SHARED": ["NVDA", "TSM"]}


def test_shared_satellites_empty_when_no_overlap():
    graph = build_dependency_graph("NVDA", _ranked())
    assert shared_satellites(graph) == {}


def test_strongest_cross_link_uses_weaker_of_the_two_edges():
    ranked_a = pd.DataFrame(
        [("SHARED", "Shared Co", "Semiconductors", 0.8)],
        columns=["ticker", "name", "sector", "correlation"],
    )
    ranked_b = pd.DataFrame(
        [("SHARED", "Shared Co", "Semiconductors", -0.6)],
        columns=["ticker", "name", "sector", "correlation"],
    )
    graph = build_multi_anchor_graph({"NVDA": ranked_a, "TSM": ranked_b})
    result = strongest_cross_link(graph)
    assert result == ("NVDA", "TSM", "SHARED", 0.6)


def test_strongest_cross_link_none_when_no_shared_satellite():
    graph = build_dependency_graph("NVDA", _ranked())
    assert strongest_cross_link(graph) is None


# --- Phase 4: richer edge metadata -------------------------------------------


def _ranked_with_phase4_columns():
    ranked = _ranked()
    ranked["stability"] = [0.9, 0.5]
    ranked["pearson_correlation"] = [0.8, -0.65]
    ranked["partial_correlation"] = [0.3, -0.2]
    ranked["sector_relative_correlation"] = [0.4, -0.1]
    ranked["best_lag"] = [2, 1]
    ranked["best_lag_correlation"] = [0.6, -0.5]
    ranked["regime_break"] = [False, True]
    ranked["regime_drift"] = [0.05, 0.5]
    return ranked


def test_edge_carries_phase4_metadata_when_present():
    graph = build_dependency_graph("NVDA", _ranked_with_phase4_columns())
    edge = graph["NVDA"]["SAT1"]
    assert edge["pearson_correlation"] == 0.8
    assert edge["partial_correlation"] == 0.3
    assert edge["sector_relative_correlation"] == 0.4
    assert edge["best_lag"] == 2
    assert edge["best_lag_correlation"] == 0.6
    assert edge["regime_break"] is False

    edge2 = graph["NVDA"]["SAT2"]
    assert edge2["regime_break"] is True


def test_edge_has_no_phase4_keys_when_columns_absent():
    graph = build_dependency_graph("NVDA", _ranked())
    edge = graph["NVDA"]["SAT1"]
    for key in ("pearson_correlation", "partial_correlation", "sector_relative_correlation", "best_lag", "regime_break"):
        assert key not in edge


# --- Phase 4: anchor relatedness ("correlation of correlations") ------------


def test_anchor_relatedness_matrix_scores_shared_satellite():
    ranked_a = pd.DataFrame(
        [("SHARED", "Shared Co", "Semiconductors", 0.8)],
        columns=["ticker", "name", "sector", "correlation"],
    )
    ranked_b = pd.DataFrame(
        [("SHARED", "Shared Co", "Semiconductors", 0.6)],
        columns=["ticker", "name", "sector", "correlation"],
    )
    graph = build_multi_anchor_graph({"NVDA": ranked_a, "TSM": ranked_b})

    matrix = anchor_relatedness_matrix(graph)

    assert matrix.loc["NVDA", "TSM"] == 0.6  # weaker of the two edges
    assert matrix.loc["TSM", "NVDA"] == 0.6  # symmetric
    assert matrix.loc["NVDA", "NVDA"] == 0.0  # zero diagonal


def test_anchor_relatedness_matrix_zero_for_unrelated_anchors():
    ranked_a = pd.DataFrame([("A_ONLY", "A Co", "Semiconductors", 0.8)], columns=["ticker", "name", "sector", "correlation"])
    ranked_b = pd.DataFrame([("B_ONLY", "B Co", "Semiconductors", 0.7)], columns=["ticker", "name", "sector", "correlation"])
    graph = build_multi_anchor_graph({"NVDA": ranked_a, "TSM": ranked_b})

    matrix = anchor_relatedness_matrix(graph)

    assert matrix.loc["NVDA", "TSM"] == 0.0


# --- Phase 4.5: JSON-ready graph serialization -------------------------------


def test_graph_to_node_link_dict_has_no_networkx_types():
    graph = build_dependency_graph("NVDA", _ranked_with_phase4_columns())
    result = graph_to_node_link_dict(graph)

    assert isinstance(result, dict)
    assert isinstance(result["nodes"], list) and isinstance(result["edges"], list)
    assert all(isinstance(n, dict) for n in result["nodes"])
    assert all(isinstance(e, dict) for e in result["edges"])


def test_graph_to_node_link_dict_node_fields():
    graph = build_dependency_graph("NVDA", _ranked(), metadata=_metadata())
    result = graph_to_node_link_dict(graph)

    by_ticker = {n["ticker"]: n for n in result["nodes"]}
    assert by_ticker["NVDA"]["kind"] == "anchor"
    assert by_ticker["SAT1"]["kind"] == "satellite"
    assert by_ticker["SAT1"]["market_cap"] == 1_000_000_000


def test_graph_to_node_link_dict_edge_fields_and_orientation():
    graph = build_dependency_graph("NVDA", _ranked_with_phase4_columns())
    result = graph_to_node_link_dict(graph)

    edge = next(e for e in result["edges"] if e["satellite"] == "SAT1")
    assert edge["anchor"] == "NVDA"
    assert edge["weight"] == 0.85
    assert edge["pearson_correlation"] == 0.8
    assert edge["best_lag"] == 2


def test_graph_to_node_link_dict_missing_metric_is_none_not_absent():
    graph = build_dependency_graph("NVDA", _ranked())  # no Phase 4 columns
    result = graph_to_node_link_dict(graph)

    edge = result["edges"][0]
    assert edge["pearson_correlation"] is None
    assert edge["regime_break"] is None
