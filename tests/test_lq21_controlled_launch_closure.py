from __future__ import annotations

import unittest
from app.services.v1_controlled_launch_closure import build_controlled_launch_closure


class LQ21ControlledLaunchClosureTests(unittest.TestCase):
    def payload(self, **overrides):
        values={"route_contract":{"ok":True,"expected_count":67,"missing_routes":[]},"admin_contract":{"ok":True,"protected_route_count":54,"unprotected_routes":[]},"migration_ledger":{"frontier_matches":True,"latest_schema_file":"056_launch_beta_validation.sql"},"environment":{"status":"ready"},"email_otp_enabled":True,"payment_links_enabled":False,"external_alerts_enabled":False}
        values.update(overrides);return build_controlled_launch_closure(**values)

    def test_controlled_launch_can_be_eligible_but_never_broadly_approved(self):
        result=self.payload();self.assertTrue(result["ok"]);self.assertEqual(result["decision"],"controlled_launch_eligible");self.assertFalse(result["broad_public_launch_approved"])

    def test_manual_gates_are_not_fabricated_as_passed(self):
        result=self.payload();self.assertTrue(all(item["status"] in {"ready_to_test","manual_required"} for item in result["manual_gates"]));self.assertFalse(result["safety"]["otp_requested"]);self.assertFalse(result["safety"]["record_mutated"])

    def test_out_of_scope_activation_holds_launch(self):
        result=self.payload(payment_links_enabled=True);self.assertFalse(result["ok"]);self.assertEqual(result["decision"],"hold_controlled_launch");self.assertIn("payments",result["excluded_from_v1"])


if __name__=="__main__":unittest.main()
