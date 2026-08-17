from __future__ import annotations

from types import SimpleNamespace

import app.services.passport_official_source_reviews as reviews
from app import create_app


class RpcQuery:
    def __init__(self, data): self.data = data; self.rpc_name = None; self.params = None
    def rpc(self, name, params): self.rpc_name = name; self.params = params; return self
    def execute(self): return SimpleNamespace(data=self.data)


def test_record_review_calls_controlled_database_function(monkeypatch):
    db = RpcQuery([{"id": "mapping-1", "verification_status": "verified"}])
    monkeypatch.setattr(reviews, "get_supabase", lambda: db)
    result = reviews.record_review("mapping-1", {
        "decision": "verified", "reviewer": "MoveReady reviewer",
        "evidence_note": "Authority and page scope independently confirmed.",
        "reviewed_source_url": "https://government.example/entry", "review_interval_days": 90,
    })
    assert result["verification_status"] == "verified"
    assert db.rpc_name == "relocation_review_passport_official_source_mapping"
    assert db.params["p_mapping_id"] == "mapping-1"
    assert db.params["p_decision"] == "verified"


def test_record_review_rejects_unsafe_payload_before_rpc(monkeypatch):
    db = RpcQuery([]); monkeypatch.setattr(reviews, "get_supabase", lambda: db)
    try:
        reviews.record_review("mapping-1", {"decision": "verified", "reviewer": "A", "evidence_note": "short", "reviewed_source_url": "http://example.com"})
        assert False, "expected ValueError"
    except ValueError:
        pass
    assert db.rpc_name is None


def test_expiry_uses_fail_closed_database_function(monkeypatch):
    db = RpcQuery(3); monkeypatch.setattr(reviews, "get_supabase", lambda: db)
    assert reviews.expire_due_reviews() == 3
    assert db.rpc_name == "relocation_expire_passport_official_source_reviews"


def test_admin_review_routes_are_registered_and_protected(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")
    app = create_app(); routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/admin/passport-official-sources/reviews" in routes
    assert "/api/admin/passport-official-sources/<mapping_id>/reviews" in routes
    assert "/api/admin/passport-official-sources/<mapping_id>/review" in routes
    assert "/api/admin/passport-official-sources/reviews/expire" in routes
    client = app.test_client()
    response = client.get("/api/admin/passport-official-sources/reviews")
    assert response.status_code in {401, 500}
