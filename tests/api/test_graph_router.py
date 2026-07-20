def test_get_graph_with_explicit_anchors(client):
    response = client.get("/api/graph", params={"anchors": ["NVDA", "TSM"]})

    assert response.status_code == 200
    body = response.json()
    tickers = {n["ticker"] for n in body["nodes"]}
    assert {"NVDA", "TSM"}.issubset(tickers)
    assert len(body["edges"]) > 0


def test_get_graph_node_has_kind_and_metadata(client):
    response = client.get("/api/graph", params={"anchors": ["NVDA"]})
    nodes_by_ticker = {n["ticker"]: n for n in response.json()["nodes"]}

    assert nodes_by_ticker["NVDA"]["kind"] == "anchor"
    assert nodes_by_ticker["SAT_HIGH"]["kind"] == "satellite"
    assert nodes_by_ticker["NVDA"]["market_cap"] == 3_000_000_000_000.0


def test_get_graph_edge_has_phase4_fields(client):
    response = client.get("/api/graph", params={"anchors": ["NVDA"]})
    edge = response.json()["edges"][0]

    assert "pearson_correlation" in edge
    assert "regime_break" in edge


def test_get_relatedness_matrix_shape(client):
    response = client.get("/api/graph/relatedness", params={"anchors": ["NVDA", "TSM"]})

    assert response.status_code == 200
    body = response.json()
    assert body["anchors"] == ["NVDA", "TSM"]
    assert len(body["matrix"]) == 2
    assert len(body["matrix"][0]) == 2
