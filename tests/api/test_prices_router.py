def test_get_prices_known_ticker(client):
    response = client.get("/api/prices/NVDA", params={"lookback_days": 100})

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "NVDA"
    assert body["lookback_days"] == 100
    assert len(body["points"]) > 0
    assert "date" in body["points"][0]
    assert "adjusted_close" in body["points"][0]


def test_get_prices_ticker_is_uppercased(client):
    response = client.get("/api/prices/nvda")
    assert response.status_code == 200
    assert response.json()["ticker"] == "NVDA"


def test_get_prices_unknown_ticker_returns_404(client):
    response = client.get("/api/prices/NOTATICKER")

    assert response.status_code == 404
    assert response.json()["ticker"] == "NOTATICKER"


def test_get_prices_uses_default_lookback_when_omitted(client):
    response = client.get("/api/prices/NVDA")

    assert response.status_code == 200
    assert response.json()["lookback_days"] > 0
