from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from flask import Flask, jsonify

from app.routes import financial_readiness, readiness_tools
from app.services.financial_readiness import (
    FinancialReadinessInputError,
    assess_financial_readiness,
)


ROUTE = {
    "country_code": "FI",
    "country_name": "Finland",
    "route_code": "study",
    "route_name": "Study pathway",
    "freshness_status": "active",
    "source_confidence": "reviewed",
    "verified_at": "2026-08-01T00:00:00Z",
    "budget_items": [
        {"item_name": "Application fees", "item_category": "visa_fee", "amount_min": 500, "amount_max": 700, "currency_code": "EUR", "notes": "Route estimate."},
        {"item_name": "Tuition", "item_category": "tuition", "amount_min": 4000, "amount_max": 4000, "currency_code": "EUR"},
        {"item_name": "Flight", "item_category": "flight", "amount_min": 600, "amount_max": 800, "currency_code": "EUR"},
        {"item_name": "Accommodation", "item_category": "accommodation", "amount_min": 1500, "amount_max": 2000, "currency_code": "EUR"},
        {"item_name": "Arrival reserve", "item_category": "settlement", "amount_min": 2000, "amount_max": 3000, "currency_code": "EUR"},
    ],
}


class FinancialReadinessServiceTests(unittest.TestCase):
    def test_complete_plan_sums_entered_resources_and_categories(self):
        result = assess_financial_readiness({
            "currency": "eur",
            "savings": 10000,
            "expected_funding": 2500,
            "family_size": 4,
            "proof_of_funds": {
                "amount": 12000,
                "currency": "EUR",
                "source_url": "https://authority.example/funds",
                "source_title": "Official funds instructions",
                "source_checked_at": "2026-08-10",
            },
            "costs": {
                "fees": 700,
                "tuition": 4000,
                "relocation": 0,
                "flight": 800,
                "accommodation": 2000,
                "settlement_reserve": 3000,
            },
            "target_timeline_months": 10,
        })

        self.assertEqual(result["contract_version"], "b09-v1")
        self.assertEqual(result["household"]["family_size"], 4)
        self.assertEqual(result["household"]["calculation_rule"], "context_only_no_invented_multiplier")
        self.assertEqual(result["resources"]["total"], 12500.0)
        self.assertEqual(result["planned_costs"]["total"], 10500.0)
        self.assertEqual(result["assessment"]["combined_target"], 22500.0)
        self.assertEqual(result["assessment"]["funding_gap"], 10000.0)
        self.assertEqual(result["assessment"]["monthly_savings_target"], 1000.0)
        self.assertEqual(result["assessment"]["status"], "funding_gap")
        self.assertEqual(result["proof_of_funds"]["status"], "user_supplied_source")

    def test_missing_requirement_fails_closed_instead_of_treating_zero_as_official(self):
        result = assess_financial_readiness({
            "currency": "EUR",
            "savings": 10000,
            "costs": {"flight": 800},
            "target_timeline_months": 6,
        })

        self.assertEqual(result["proof_of_funds"]["status"], "requirement_not_provided")
        self.assertEqual(result["assessment"]["status"], "requirements_needed")
        self.assertIsNone(result["assessment"]["combined_target"])
        self.assertIsNone(result["assessment"]["funding_gap"])
        self.assertIsNone(result["assessment"]["monthly_savings_target"])

    def test_family_size_never_changes_an_entered_requirement(self):
        base = {
            "currency": "CAD",
            "savings": 12000,
            "proof_of_funds": {"amount": 15000, "source_url": "https://authority.example/funds"},
            "target_timeline_months": 6,
        }
        one = assess_financial_readiness({**base, "family_size": 1})
        four = assess_financial_readiness({**base, "family_size": 4})

        self.assertEqual(one["proof_of_funds"]["amount"], 15000.0)
        self.assertEqual(four["proof_of_funds"]["amount"], 15000.0)
        self.assertEqual(one["assessment"]["funding_gap"], 3000.0)
        self.assertEqual(four["assessment"]["funding_gap"], 3000.0)
        self.assertTrue(any("does not trigger" in warning for warning in four["warnings"]))

    def test_currency_mismatch_blocks_combined_calculation(self):
        result = assess_financial_readiness({
            "currency": "EUR",
            "savings": 12000,
            "proof_of_funds": {
                "amount": 10000,
                "currency": "CAD",
                "source_url": "https://authority.example/funds",
            },
            "costs": {"flight": 1000},
        })

        self.assertEqual(result["assessment"]["status"], "currency_mismatch")
        self.assertTrue(result["assessment"]["currency_mismatch"])
        self.assertIsNone(result["assessment"]["combined_target"])
        self.assertIsNone(result["assessment"]["funding_gap"])

    def test_target_date_uses_remaining_calendar_months(self):
        result = assess_financial_readiness({
            "currency": "EUR",
            "savings": 0,
            "proof_of_funds": {"amount": 1200, "source_url": "https://authority.example/funds"},
            "target_date": "2027-02-17",
        }, today=date(2026, 8, 17))

        self.assertEqual(result["target"]["months_remaining"], 6)
        self.assertEqual(result["assessment"]["monthly_savings_target"], 200.0)

    def test_invalid_negative_money_is_rejected(self):
        with self.assertRaises(FinancialReadinessInputError) as context:
            assess_financial_readiness({"currency": "EUR", "savings": -1})
        self.assertEqual(context.exception.field, "savings")

    def test_non_https_proof_source_is_rejected(self):
        with self.assertRaises(FinancialReadinessInputError) as context:
            assess_financial_readiness({
                "currency": "EUR",
                "proof_of_funds": {"amount": 1000, "source_url": "http://authority.example/funds"},
            })
        self.assertEqual(context.exception.code, "https_source_url_required")

        with self.assertRaises(FinancialReadinessInputError):
            assess_financial_readiness({
                "currency": "EUR",
                "proof_of_funds": {"amount": 1000, "source_url": "https://"},
            })

    def test_user_cost_cannot_claim_route_estimate_provenance(self):
        result = assess_financial_readiness({
            "currency": "EUR",
            "proof_of_funds": {"amount": 0, "source_url": "https://authority.example/funds"},
            "costs": {"fees": {"amount": 100, "source_type": "route_estimate"}},
        })
        self.assertEqual(result["planned_costs"]["items"][0]["source_type"], "user_entered")


class FinancialReadinessRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SECRET_KEY="b09-route-tests")
        self.app.register_blueprint(financial_readiness.bp, url_prefix="/api/financial-readiness")
        self.app.register_blueprint(readiness_tools.bp, url_prefix="/api/readiness")
        self.client = self.app.test_client()
        self.patchers = [
            patch.object(financial_readiness, "_route", lambda country, route: ROUTE),
            patch.object(
                readiness_tools,
                "_with_storage",
                lambda _slug, _payload, result: jsonify({**result, "stored": False}),
            ),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()

    def test_route_check_exposes_b09_plan_and_preserves_legacy_cost_assessment(self):
        response = self.client.post("/api/financial-readiness/check", json={
            "country_code": "FI",
            "route_code": "study",
            "currency": "EUR",
            "available_funds": 10000,
            "expected_funding": 2500,
            "family_size": 4,
            "proof_of_funds": {
                "amount": 12000,
                "source_url": "https://authority.example/funds",
                "source_title": "Official funds instructions",
            },
            "target_timeline_months": 10,
        })

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["contract_version"], "b09-v1")
        self.assertEqual(payload["estimated_costs"]["minimum"], 8600.0)
        self.assertEqual(payload["estimated_costs"]["maximum"], 10500.0)
        self.assertEqual(payload["assessment"]["gap_to_estimated_minimum"], 0.0)
        self.assertEqual(payload["financial_plan"]["planned_costs"]["by_category"]["fees"], 700.0)
        self.assertEqual(payload["financial_plan"]["assessment"]["funding_gap"], 10000.0)
        self.assertEqual(payload["financial_plan"]["assessment"]["monthly_savings_target"], 1000.0)

    def test_user_cost_category_replaces_same_route_estimate_category(self):
        response = self.client.post("/api/financial-readiness/check", json={
            "country_code": "FI",
            "route_code": "study",
            "currency": "EUR",
            "available_funds": 0,
            "proof_of_funds": {"amount": 0, "source_url": "https://authority.example/funds"},
            "costs": {"fees": 100},
        })
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["financial_plan"]["planned_costs"]["by_category"]["fees"], 100.0)
        self.assertEqual(payload["financial_plan"]["planned_costs"]["total"], 9900.0)

    def test_legacy_funds_plan_removes_invented_family_multiplier(self):
        response = self.client.post("/api/readiness/funds-plan", json={
            "available_funds_amount": 12000,
            "required_funds_amount": 15000,
            "target_timeline_months": 6,
            "family_members_count": 3,
            "currency": "CAD",
            "proof_of_funds_source_url": "https://authority.example/funds",
        })
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["contract_version"], "b09-v1")
        self.assertEqual(payload["household"]["family_size"], 4)
        self.assertEqual(payload["required_funds_adjusted"], 15000.0)
        self.assertEqual(payload["shortfall"], 3000.0)
        self.assertEqual(payload["monthly_savings_target"], 500.0)
        self.assertFalse(payload["stored"])

    def test_invalid_payload_returns_specific_400(self):
        response = self.client.post("/api/readiness/funds-plan", json={
            "available_funds_amount": -1,
            "required_funds_amount": 1000,
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["field"], "savings")


if __name__ == "__main__":
    unittest.main()
