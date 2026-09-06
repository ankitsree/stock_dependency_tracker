"""POST /api/portfolio/analyze.

The `client` fixture's synthetic universe (tests/api/conftest.py) has price
data for NVDA/TSM/SAT_HIGH/SAT_LOW but not for config.yaml's other anchors
(AAPL, ASML) — so these also cover the "anchor without data gets dropped"
path end-to-end.
"""

MAX_HOLDINGS = 50


def _analyze(client, holdings, **body):
    return client.post("/api/portfolio/analyze", json={"holdings": holdings, **body})


def test_analyze_returns_a_full_decomposition(client):
    response = _analyze(client, [{"ticker": "SAT_HIGH", "shares": 100}, {"ticker": "SAT_LOW", "shares": 50}])

    assert response.status_code == 200
    body = response.json()
    weights = [h["weight"] for h in body["holdings"]]
    assert weights == sorted(weights, reverse=True)
    assert sum(weights) == 1.0
    assert sum(f["share"] for f in body["factor_exposure"]) == 1.0
    assert body["risk_summary"]
    assert body["lookback_days"] > 0
    assert body["generated_at"]


def test_anchors_without_price_data_are_excluded(client):
    response = _analyze(client, [{"ticker": "SAT_HIGH", "shares": 1}])

    assert response.json()["anchors"] == ["NVDA", "TSM"]


def test_exactly_one_idiosyncratic_slice_is_returned(client):
    response = _analyze(client, [{"ticker": "SAT_HIGH", "shares": 1}])

    factors = response.json()["factor_exposure"]
    assert [f["factor"] for f in factors if f["is_idiosyncratic"]] == ["idiosyncratic"]
    # The residual is always last so the pie legend reads named-factors-first.
    assert factors[-1]["is_idiosyncratic"] is True


def test_a_satellite_that_tracks_an_anchor_loads_onto_it(client):
    response = _analyze(client, [{"ticker": "SAT_HIGH", "shares": 1}])

    body = response.json()
    assert body["concentration"]["top_factor"] in {"NVDA", "TSM"}
    assert body["concentration"]["top_factor_share"] > 0.5
    assert body["holdings"][0]["correlations"]["NVDA"] > 0.8


def test_explicit_anchors_are_honoured_and_upper_cased(client):
    response = _analyze(client, [{"ticker": "SAT_HIGH", "shares": 1}], anchors=["nvda"])

    assert response.json()["anchors"] == ["NVDA"]


def test_lower_case_tickers_are_accepted(client):
    response = _analyze(client, [{"ticker": "sat_high", "shares": 1}])

    assert response.status_code == 200
    assert response.json()["holdings"][0]["ticker"] == "SAT_HIGH"


def test_unknown_tickers_are_reported_as_unresolved(client):
    response = _analyze(client, [{"ticker": "SAT_HIGH", "shares": 1}, {"ticker": "NOTATICKER", "shares": 1}])

    assert response.status_code == 200
    assert [u["ticker"] for u in response.json()["unresolved"]] == ["NOTATICKER"]


def test_omitting_share_counts_falls_back_to_equal_weighting(client):
    response = _analyze(client, [{"ticker": "SAT_HIGH"}, {"ticker": "SAT_LOW"}])

    body = response.json()
    assert body["weighting"] == "equal"
    assert body["total_value"] is None


def test_a_portfolio_with_no_usable_holdings_returns_422(client):
    response = _analyze(client, [{"ticker": "NOTATICKER", "shares": 1}])

    assert response.status_code == 422


def test_an_empty_holdings_list_is_rejected(client):
    response = _analyze(client, [])

    assert response.status_code == 422


def test_more_holdings_than_the_cap_are_rejected(client):
    response = _analyze(client, [{"ticker": f"T{i}", "shares": 1} for i in range(MAX_HOLDINGS + 1)])

    assert response.status_code == 422


def test_non_positive_share_counts_are_rejected(client):
    response = _analyze(client, [{"ticker": "SAT_HIGH", "shares": 0}])

    assert response.status_code == 422
