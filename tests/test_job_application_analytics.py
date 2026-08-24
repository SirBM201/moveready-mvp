import pytest

from app.services.job_application_analytics import attribution_breakdown, funnel_flags, metrics, outcome_attribution


def application(job_id, state, **extra):
    row={"job_id":job_id,"pipeline_state":state,"readiness_state":"ready","title":"Engineer","company":"Example","country":"Canada","source":"official"}
    row.update(extra);return row


def test_outcome_attribution_uses_recorded_fields_without_inferred_feedback():
    result=outcome_attribution(application("j1","interview"))
    assert result["positive_outcome"] is True
    assert result["country"]=="Canada"
    assert result["employer"]=="Example"
    assert result["employer_feedback_inferred"] is False


def test_funnel_is_cumulative_after_submission():
    flags=funnel_flags(application("j1","offer",draft_id="d1"))
    assert flags["tracked"] and flags["ready"] and flags["drafted"] and flags["submitted"] and flags["interview"] and flags["offer"]
    assert flags["hired"] is False


def test_metrics_calculates_submission_and_outcome_rates():
    rows=[application("j1","submitted"),application("j2","interview"),application("j3","offer"),application("j4","hired")]
    result=metrics(rows)
    assert result["applications_tracked"]==4
    assert result["funnel"]["submitted"]==4
    assert result["funnel"]["interview"]==3
    assert result["rates"]["interview_per_submission"]==0.75
    assert result["rates"]["hire_per_submission"]==0.25


def test_terminal_outcomes_are_counted_without_guessing_reason():
    result=metrics([application("j1","rejected"),application("j2","withdrawn"),application("j3","hired")])
    assert result["terminal_outcomes"]=={"rejected":1,"withdrawn":1,"hired":1}
    assert result["safety"]["employer_feedback_inferred"] is False


def test_attribution_breakdown_groups_by_recorded_source():
    rows=[application("j1","submitted",source="official"),application("j2","interview",source="official"),application("j3","submitted",source="aggregator")]
    result=attribution_breakdown(rows,"source")
    assert result[0]["value"]=="official"
    assert result[0]["applications"]==2
    assert result[0]["rates"]["interview_per_submission"]==0.5


def test_unknown_dimension_is_rejected():
    with pytest.raises(ValueError,match="unsupported_attribution_dimension"):
        attribution_breakdown([],"salary")
