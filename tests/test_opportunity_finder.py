from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app import create_app
from app.services.opportunity_finder import recommend_pathways


NOW = datetime(2026, 8, 17, tzinfo=timezone.utc)
ROUTE = {
    "id": "route-1",
    "active_version_id": "version-1",
    "route_code": "specialist",
    "route_name": "Specialist work route",
    "route_category": "work",
    "country_id": "country-1",
    "country_code": "FI",
    "country_name": "Finland",
    "summary": "A reviewed work route summary.",
    "risk_level": "medium",
    "source_confidence": "high",
    "verified_at": "2026-08-01T00:00:00Z",
    "review_due_at": "2026-09-01T00:00:00Z",
    "version": {
        "eligibility_notes": "Check the applicant and employer against the current route rules.",
        "processing_time_notes": "Processing time varies by application and authority workload.",
        "validity_notes": "Confirm validity on the decision and official instructions.",
        "refusal_risk_notes": "Incomplete purpose evidence can create refusal risk.",
    },
    "documents": [
        {"document_name": "Passport", "requirement_level": "required", "applies_to": "applicant", "details": "Valid passport."},
        {"document_name": "Employer evidence", "requirement_level": "conditional", "applies_to": "applicant", "details": "Depends on the route basis."},
    ],
    "budget_items": [
        {"item_name": "Application fee", "item_category": "visa_fee", "amount_min": 350, "amount_max": 500, "currency_code": "EUR", "is_required": True},
    ],
    "official_sources": [{
        "source_name": "Finnish Immigration Service",
        "source_url": "https://migri.example/specialist",
        "source_type": "government",
        "owner_organization": "Finnish Immigration Service",
        "reliability_level": "high",
        "status": "active",
        "last_checked_at": "2026-08-01T00:00:00Z",
        "next_review_due_at": "2026-09-01T00:00:00Z",
        "usage_note": "Eligibility and application instructions.",
    }],
}


class OpportunityFinderTests(unittest.TestCase):
    def test_work_goal_and_experience_prioritize_work(self):
        result = recommend_pathways({
            "main_goal": "work",
            "work_experience_years": 8,
            "target_country": "Finland",
            "education_level": "OND",
            "available_funds_amount": 10000,
        }, routes=[ROUTE], retrieved_at=NOW)

        recommendation = result["recommendations"][0]
        self.assertEqual(result["contract_version"], "b11-v1")
        self.assertEqual(recommendation["pathway"], "work")
        self.assertGreaterEqual(recommendation["fit_score"], 70)
        self.assertEqual(recommendation["score_kind"], "profile_alignment_not_eligibility")
        self.assertEqual(recommendation["qualification"]["decision"], "not_determined")

    def test_route_candidate_exposes_evidence_cost_timeline_risk_and_sources(self):
        result = recommend_pathways({"main_goal": "work", "target_country": "Finland"}, routes=[ROUTE], retrieved_at=NOW)
        candidate = result["recommendations"][0]["candidate_routes"][0]

        self.assertEqual(candidate["evidence"]["required_count"], 1)
        self.assertEqual(candidate["evidence"]["conditional_count"], 1)
        self.assertEqual(candidate["costs"]["minimum"], 350.0)
        self.assertEqual(candidate["costs"]["maximum"], 500.0)
        self.assertTrue(candidate["costs"]["planning_only"])
        self.assertEqual(len(candidate["timeline_notes"]), 2)
        self.assertTrue(candidate["risk_notes"])
        self.assertEqual(candidate["provenance"]["jurisdiction"], "Finland")
        self.assertEqual(candidate["provenance"]["official_source_status"], "official_sources_current")
        self.assertEqual(candidate["official_sources"][0]["url"], "https://migri.example/specialist")
        self.assertEqual(candidate["next_actions"][0]["href"], "/route-checker?country=FI&route=specialist")

    def test_source_provenance_fails_closed_when_unverified_or_non_https(self):
        unsafe = {
            **ROUTE,
            "verified_at": None,
            "official_sources": [{**ROUTE["official_sources"][0], "source_url": "http://not-secure.example"}],
        }
        result = recommend_pathways({"main_goal": "work"}, routes=[unsafe], retrieved_at=NOW)
        candidate = result["recommendations"][0]["candidate_routes"][0]

        self.assertEqual(candidate["provenance"]["freshness_status"], "verification_missing")
        self.assertEqual(candidate["provenance"]["official_source_status"], "source_review_required")
        self.assertEqual(candidate["official_sources"], [])

    def test_business_profile_surfaces_founder_routes(self):
        result = recommend_pathways({"main_goal": "startup", "business_stage": "operating", "available_funds_amount": 15000}, retrieved_at=NOW)
        keys = [item["pathway"] for item in result["recommendations"][:3]]
        self.assertIn("startup", keys)
        self.assertIn("business", keys)

    def test_finder_exposes_gaps_no_guarantee_and_privacy_safe_snapshot(self):
        result = recommend_pathways({"main_goal": "relocation", "email": "private@example.com", "full_name": "Private Person"}, retrieved_at=NOW)

        self.assertTrue(result["profile_gaps"])
        self.assertIn("not eligibility", result["safety_note"].lower())
        self.assertNotIn("email", result["profile_snapshot"])
        self.assertNotIn("full_name", result["profile_snapshot"])


class OpportunityFinderPrivacyTests(unittest.TestCase):
    def test_recommendations_require_verified_account_session(self):
        app = create_app()
        app.config.update(TESTING=True, SECRET_KEY="b11-privacy-test")
        response = app.test_client().get("/api/opportunity-finder/recommendations")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "verified_session_required")


if __name__ == "__main__":
    unittest.main()
