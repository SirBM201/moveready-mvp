from app.services.job_offer_mobility_handoff import build_offer_mobility_handoff


def test_unconfirmed_offer_cannot_start_mobility_handoff():
    result=build_offer_mobility_handoff(job={"id":"j1","country":"Canada"},lifecycle={"state":"interview"},profile={})
    assert result["available"] is False
    assert result["ready_for_mobility_planning"] is False
    assert result["gaps"][0]["code"]=="confirmed_offer_required"


def test_offer_does_not_override_work_route_evidence():
    result=build_offer_mobility_handoff(job={"id":"j1","country":"Canada","visa_sponsorship_status":"unknown"},lifecycle={"state":"offer","latest_evidence":{"type":"offer_document"}},profile={"work_authorized_countries":[]})
    assert result["available"] is True
    assert result["ready_for_mobility_planning"] is False
    assert any(row["code"]=="work_route_unconfirmed" for row in result["gaps"])
    assert result["safety"]["offer_is_not_immigration_approval"] is True


def test_confirmed_work_route_opens_mobility_planning_without_booking():
    result=build_offer_mobility_handoff(job={"id":"j1","job_title":"Engineer","country":"Canada","visa_sponsorship_status":"confirmed","relocation_support_status":"confirmed"},lifecycle={"state":"offer","latest_evidence":{"type":"offer_document","start_date":"2026-10-01"}},profile={})
    assert result["ready_for_mobility_planning"] is True
    assert result["next_actions"][0]["action"]=="build_mobility_plan"
    assert result["safety"]["travel_booking_performed"] is False
