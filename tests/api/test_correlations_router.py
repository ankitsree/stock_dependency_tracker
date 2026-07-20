def test_get_correlations_returns_ranked_satellites(client):
    response = client.get("/api/anchors/NVDA/correlations")

    assert response.status_code == 200
    body = response.json()
    assert body["anchor"] == "NVDA"
    tickers = [s["ticker"] for s in body["satellites"]]
    assert "SAT_HIGH" in tickers
    assert "SAT_LOW" not in tickers  # below default threshold
    assert body["cache_hit"] is False


def test_get_correlations_second_call_is_cache_hit(client):
    client.get("/api/anchors/NVDA/correlations")
    response = client.get("/api/anchors/NVDA/correlations")

    assert response.json()["cache_hit"] is True


def test_post_refresh_bypasses_cache(client):
    client.get("/api/anchors/NVDA/correlations")
    response = client.post("/api/anchors/NVDA/refresh")

    assert response.status_code == 200
    assert response.json()["cache_hit"] is False


def test_get_correlations_unknown_anchor_returns_404(client):
    response = client.get("/api/anchors/NOTATICKER/correlations")

    assert response.status_code == 404


def test_get_correlations_respects_top_n_query_param(client):
    response = client.get("/api/anchors/NVDA/correlations", params={"top_n": 1, "threshold": 0})

    assert response.status_code == 200
    assert len(response.json()["satellites"]) == 1


def test_get_correlations_satellite_has_full_diagnostic_fields(client):
    response = client.get("/api/anchors/NVDA/correlations")
    satellite = response.json()["satellites"][0]

    for field in ("stability", "pearson_correlation", "partial_correlation", "sector_relative_correlation"):
        assert field in satellite
