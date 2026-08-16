from app.services.financial_readiness import assess_financial_readiness


def test_financial_readiness_ready():
    result = assess_financial_readiness({
        "currency": "cad",
        "available_funds": 25000,
        "proof_of_funds_required": 15000,
        "estimated_relocation_cost": 5000,
        "settlement_reserve": 3000,
    })
    assert result["currency"] == "CAD"
    assert result["target_funds"] == 23000.0
    assert result["funding_gap"] == 0.0
    assert result["surplus"] == 2000.0
    assert result["readiness_score"] == 100
    assert result["status"] == "ready"


def test_financial_readiness_reports_gap():
    result = assess_financial_readiness({
        "available_funds": 10000,
        "proof_of_funds_required": 12000,
        "estimated_relocation_cost": 3000,
        "settlement_reserve": 2000,
    })
    assert result["target_funds"] == 17000.0
    assert result["funding_gap"] == 7000.0
    assert result["status"] == "building"


def test_financial_readiness_requires_known_target():
    result = assess_financial_readiness({"available_funds": 10000})
    assert result["status"] == "requirements_needed"
