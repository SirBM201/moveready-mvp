from app.services.job_application_portfolio_reconciliation import build_corrective_plan, validate_corrective_operation


def test_terminal_followups_generate_only_supersession_plan():
    plan=build_corrective_plan(lifecycle={"id":"l1","state":"hired"},followups=[{"id":"f1","status":"due"},{"id":"f2","status":"completed"}])
    assert plan["safe_to_execute"] is True
    assert plan["operations"][0]["followup_updates"]=={"f1":"superseded"}


def test_non_terminal_lifecycle_generates_no_corrective_write():
    plan=build_corrective_plan(lifecycle={"id":"l1","state":"interview"},followups=[{"id":"f1","status":"due"}])
    assert plan["operations"]==[]


def test_unknown_corrective_operation_is_rejected():
    result=validate_corrective_operation({"operation":"change_lifecycle_state","followup_updates":{"f1":"superseded"}})
    assert result["ok"] is False
    assert result["error"]=="portfolio_corrective_operation_not_allowed"


def test_corrective_operation_cannot_set_arbitrary_followup_status():
    result=validate_corrective_operation({"operation":"supersede_terminal_followups","followup_updates":{"f1":"completed"}})
    assert result["ok"] is False
    assert result["error"]=="unsafe_followup_target_status"
