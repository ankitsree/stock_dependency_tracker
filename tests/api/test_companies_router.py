def test_list_companies_without_market_data(client):
    response = client.get("/api/companies")

    assert response.status_code == 200
    companies = response.json()["companies"]
    assert {c["ticker"] for c in companies} == {"SAT_HIGH", "SAT_LOW"}
    assert companies[0]["market_cap"] is None


def test_list_companies_with_market_data(client):
    response = client.get("/api/companies", params={"include_market_data": True})

    assert response.status_code == 200
    by_ticker = {c["ticker"]: c for c in response.json()["companies"]}
    assert by_ticker["SAT_HIGH"]["market_cap"] == 1_000_000_000.0


def test_get_company_known_satellite(client):
    response = client.get("/api/companies/SAT_HIGH")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "High Corr Co"
    assert body["market_cap"] == 1_000_000_000.0


def test_get_company_anchor_not_in_universe_still_resolves(client):
    response = client.get("/api/companies/NVDA")

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "NVDA"
    assert body["sector"] == "Unknown"
    assert body["market_cap"] == 3_000_000_000_000.0


def test_get_company_unknown_ticker_returns_404(client):
    response = client.get("/api/companies/NOTATICKER")

    assert response.status_code == 404
