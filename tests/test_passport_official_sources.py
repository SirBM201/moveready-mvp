from __future__ import annotations

from types import SimpleNamespace

import app.services.passport_official_sources as official


class FakeQuery:
    def __init__(self, db, table):
        self.db = db
        self.table_name = table
        self.filters = []

    def table(self, name): return FakeQuery(self.db, name)
    def select(self, _columns): return self
    def eq(self, column, value): self.filters.append(("eq", column, value)); return self
    def neq(self, column, value): self.filters.append(("neq", column, value)); return self
    def ilike(self, column, value): self.filters.append(("eq", column, value)); return self
    def limit(self, _value): return self
    def order(self, _column): return self
    def execute(self):
        rows = list(self.db.get(self.table_name, []))
        for op, column, value in self.filters:
            if op == "eq": rows = [r for r in rows if r.get(column) == value]
            if op == "neq": rows = [r for r in rows if r.get(column) != value]
        return SimpleNamespace(data=rows)


class FakeDb(FakeQuery):
    def __init__(self, data):
        self.db = data
        self.table_name = ""
        self.filters = []


def test_pending_government_source_is_exposed_but_not_verified(monkeypatch):
    data = {
        "relocation_countries": [{"id": "ca", "country_name": "Canada"}],
        "relocation_passport_official_source_mappings": [{
            "destination_country_id": "ca", "source_id": "ircc", "purpose": "entry_requirements",
            "priority": 10, "status": "active", "verification_status": "pending_review",
            "verified_at": None, "review_due_at": "2026-09-15T00:00:00+00:00",
        }],
        "relocation_trusted_sources": [{
            "id": "ircc", "source_name": "Government of Canada - Visit Canada",
            "owner_organization": "Immigration, Refugees and Citizenship Canada (IRCC)",
            "source_type": "government", "reliability_level": "high", "status": "active",
            "source_url": "https://www.canada.ca/visit",
        }],
    }
    monkeypatch.setattr(official, "get_supabase", lambda: FakeDb(data))
    result = official.enrich_destination_result({"destination": "Canada", "detail": {"source_status": "provider_detail_pending_official_confirmation"}})
    assert len(result["official_sources"]) == 1
    assert result["official_sources"][0]["verification_status"] == "pending_review"
    assert result["official_sources"][0]["verified"] is False
    assert result["official_source_layer"]["verified_count"] == 0
    assert result["detail"]["source_status"] == "provider_detail_pending_official_confirmation"


def test_non_government_mapping_fails_closed(monkeypatch):
    data = {
        "relocation_countries": [{"id": "ca", "country_name": "Canada"}],
        "relocation_passport_official_source_mappings": [{
            "destination_country_id": "ca", "source_id": "third", "purpose": "entry_requirements",
            "priority": 10, "status": "active", "verification_status": "verified", "verified_at": "2026-08-16T00:00:00+00:00",
        }],
        "relocation_trusted_sources": [{
            "id": "third", "source_name": "Provider", "owner_organization": "Provider",
            "source_type": "commercial", "reliability_level": "medium", "status": "active",
            "source_url": "https://example.com",
        }],
    }
    monkeypatch.setattr(official, "get_supabase", lambda: FakeDb(data))
    assert official.official_sources_for_destination("Canada") == []
