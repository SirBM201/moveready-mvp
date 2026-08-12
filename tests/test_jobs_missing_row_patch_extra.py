from __future__ import annotations

from types import SimpleNamespace

import app.services.job_automation_profile_patch as patch


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def table(self, _name): return self
    def select(self, _columns): return self
    def eq(self, _column, _value): return self
    def limit(self, _value): return self
    def execute(self): return SimpleNamespace(data=self.rows)


def test_safe_visible_company_preserves_visibility(monkeypatch):
    query = FakeQuery([{"id": "company-1", "is_curated": False, "owner_email": "owner@example.com"}])
    monkeypatch.setattr(patch, "get_supabase", lambda: query)
    assert patch._safe_visible_company("company-1", "owner@example.com") is not None
    assert patch._safe_visible_company("company-1", "other@example.com") is None


def test_patch_hardens_core_jobs_module():
    automation = SimpleNamespace(_profile=None)
    from app.routes import jobs
    patch.apply_job_automation_profile_patch(automation)
    assert automation._profile is patch._safe_profile
    assert jobs._profile is patch._safe_profile
    assert jobs._owned_row is patch._safe_owned_row
    assert jobs._visible_company is patch._safe_visible_company
    assert jobs._visible_job is patch._safe_visible_job
