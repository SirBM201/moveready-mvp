from app import create_app


def _routes(app):
    return {rule.rule for rule in app.url_map.iter_rules()}


def test_v1_completion_routes_are_registered(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")
    app = create_app()
    routes = _routes(app)
    expected = {
        "/api/opportunity-finder/recommendations",
        "/api/financial-readiness/check",
        "/api/route-comparison",
        "/api/account/outcomes",
        "/api/language-coach/profile",
    }
    assert expected.issubset(routes), sorted(expected - routes)


def test_build_info_reports_v1_safety_contract(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")
    app = create_app()
    client = app.test_client()
    response = client.get("/api/build-info")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["route_contract"]["ok"] is True
    assert payload["contract_versions"]["financial_readiness"] == "b09-v1"
    assert payload["contract_versions"]["opportunity_finder"] == "b11-v1"
    safety = payload["safety_contract"]
    for key in ("opportunity_finder", "route_comparison", "financial_readiness", "account_outcomes"):
        assert key in safety
    assert "no invented family multiplier" in safety["financial_readiness"].lower()
    features = payload["features"]
    for key in ("opportunity_finder", "route_comparison", "financial_readiness", "account_outcomes", "language_coach", "readiness_command_center"):
        assert features[key] is True
