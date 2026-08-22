from pathlib import Path

from app.services.job_application_handoff import approve_package, build_controlled_handoff, build_package_review

ROOT = Path(__file__).resolve().parents[1]


def _draft(status="reviewed"):
    return {
        "id": "draft-1",
        "job_id": "job-1",
        "status": status,
        "source_fingerprint": "vacancy-fingerprint-1",
        "cv_draft": {"target_title": "Manufacturing Technician"},
        "cover_letter_draft": {"opening": "Application"},
        "application_answers": {"status": "not_required_or_not_detected"},
    }


def test_full_review_approval_handoff_contract_keeps_user_in_control():
    readiness = {"state": "ready_to_apply"}
    review = build_package_review(_draft(), readiness)
    assert review["ok"] is True

    approval = approve_package(_draft(), readiness, user_confirmed=True)
    assert approval["approved"] is True
    assert approval["submission_allowed"] is False

    handoff = build_controlled_handoff(
        _draft("approved"),
        {"application_url": "https://employer.example/apply"},
        approved=True,
    )
    assert handoff["ok"] is True
    assert handoff["safety"]["user_must_trigger_submission"] is True
    assert handoff["safety"]["auto_submit_allowed"] is False


def test_stale_draft_cannot_cross_approval_boundary():
    review = build_package_review(_draft("stale"), {"state": "ready_to_apply"})
    assert review["ok"] is False
    assert "application_draft_is_stale" in review["blockers"]


def test_unapproved_persisted_draft_cannot_create_handoff():
    handoff = build_controlled_handoff(
        _draft("reviewed"),
        {"source_url": "https://employer.example/job"},
        approved=True,
    )
    assert handoff["ok"] is False
    assert handoff["error"] == "approved_application_package_required"


def test_b19_6_route_contract_is_registered_and_manual_only():
    route = (ROOT / "app/routes/job_application_handoffs.py").read_text(encoding="utf-8")
    app_init = (ROOT / "app/__init__.py").read_text(encoding="utf-8")
    migration = (ROOT / "supabase/migrations/047_job_application_handoffs.sql").read_text(encoding="utf-8")

    assert 'CONTRACT_VERSION = "b19.6-v1"' in route
    assert 'action not in {"opened", "submitted_manual", "withdrawn"}' in route
    assert '"autonomous_submission": False' in route
    assert '"user_action_required": True' in route
    assert "job_application_handoffs" in app_init
    assert "relocation_job_application_handoffs" in migration
    assert "relocation_job_application_handoff_events" in migration
    assert "submitted_manual" in migration


def test_handoff_snapshot_binds_vacancy_specific_materials():
    route = (ROOT / "app/routes/job_application_handoffs.py").read_text(encoding="utf-8")
    for field in ("source_fingerprint", "cv_draft", "cover_letter_draft", "application_answers"):
        assert field in route
    assert 'draft.get("status") != "approved"' in route
