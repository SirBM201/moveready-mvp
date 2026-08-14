from app import create_app


def _routes(app):
    return {rule.rule for rule in app.url_map.iter_rules()}


def test_v1_completion_routes_are_registered(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")
    app = create_app()
    routes = _routes(app)
    expected = {
        "/api/v1/opportunity-finder/recommendations",
        "/api/v1/financial-readiness/check",
        "/api/v1/route-comparison",
        "/api/v1/account/outcomes",
        "/api/v1/language-coach/profile",
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
    safety = payload["safety_contract"]
    for key in ("opportunity_finder", "route_comparison", "financial_readiness", "account_outcomes"):
        assert key in safety
    features = payload["features"]
    for key in ("opportunity_finder", "route_comparison", "financial_readiness", "account_outcomes", "language_coach", "readiness_command_center"):
        assert features[key] is True
