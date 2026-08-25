from pathlib import Path

ROUTE = Path("app/routes/job_employers.py").read_text(encoding="utf-8")

def test_lq08_employer_intelligence_routes_are_user_scoped_and_safe():
    assert '@bp.get("/employers")' in ROUTE
    assert '@bp.post("/campaigns/<campaign_id>/employers/<employer_id>/target")' in ROUTE
    assert 'eq("email",email)' in ROUTE
    assert 'TARGET_TYPES={"priority","watch","excluded"}' in ROUTE
    assert '"employer_verified":False' in ROUTE
    assert '"sponsorship_proven":False' in ROUTE
    assert '"employer_interest_proven":False' in ROUTE
