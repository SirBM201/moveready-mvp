from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "job_authorization.py"
SPEC = importlib.util.spec_from_file_location("job_authorization", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
extract_authorization_signals = MODULE.extract_authorization_signals


class JobAuthorizationTests(unittest.TestCase):
    def test_existing_authorization_and_no_sponsorship_are_detected(self):
        result = extract_authorization_signals({
            "description_summary": "Applicants must currently be authorized to work in Canada. No visa sponsorship is available."
        })
        self.assertEqual(result["work_authorization_requirement"], "existing_required")
        self.assertEqual(result["visa_sponsorship_status"], "not_available")
        self.assertTrue(result["authorization_evidence"])

    def test_confirmed_sponsorship_and_relocation_are_detected(self):
        result = extract_authorization_signals({
            "description_summary": "Visa sponsorship is available for this position. Relocation assistance is provided."
        })
        self.assertEqual(result["work_authorization_requirement"], "employer_support_confirmed")
        self.assertEqual(result["visa_sponsorship_status"], "confirmed")
        self.assertEqual(result["relocation_support_status"], "confirmed")

    def test_possible_sponsorship_does_not_become_confirmed(self):
        result = extract_authorization_signals({
            "description_summary": "Visa sponsorship may be considered for exceptional candidates."
        })
        self.assertEqual(result["work_authorization_requirement"], "employer_support_possible")
        self.assertEqual(result["visa_sponsorship_status"], "possible")

    def test_unknown_text_stays_unknown(self):
        result = extract_authorization_signals({
            "description_summary": "Join our manufacturing team and improve production performance."
        })
        self.assertEqual(result["work_authorization_requirement"], "unknown")
        self.assertEqual(result["visa_sponsorship_status"], "unknown")
        self.assertEqual(result["relocation_support_status"], "unknown")
        self.assertEqual(result["authorization_evidence"], [])

    def test_negative_sponsorship_wins_if_source_is_conflicting(self):
        result = extract_authorization_signals({
            "description_summary": "Visa sponsorship may be considered. However, no visa sponsorship is available for this vacancy."
        })
        self.assertEqual(result["work_authorization_requirement"], "existing_required")
        self.assertEqual(result["visa_sponsorship_status"], "not_available")


if __name__ == "__main__":
    unittest.main()
