from datetime import date
import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "job_actions.py"
SPEC = importlib.util.spec_from_file_location("job_actions", MODULE_PATH)
assert SPEC and SPEC.loader
JOB_ACTIONS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(JOB_ACTIONS)
build_job_actions = JOB_ACTIONS.build_job_actions
count_job_actions = JOB_ACTIONS.count_job_actions
company_target_status = JOB_ACTIONS.company_target_status


class JobActionTests(unittest.TestCase):
    def test_combines_overdue_application_and_upcoming_recruiter_actions(self):
        actions = build_job_actions(
            [{
                "id": "application-1",
                "job_title": "Production Supervisor",
                "company_name": "Example Plastics",
                "status": "applied",
                "follow_up_date": "2026-08-09",
            }],
            [{
                "id": "recruiter-1",
                "recruiter_name": "Jordan Lee",
                "recruitment_company": "Manufacturing Search",
                "connection_status": "contacted",
                "follow_up_date": "2026-08-13",
            }],
            today=date(2026, 8, 11),
        )

        self.assertEqual([item["kind"] for item in actions], [
            "job_application_follow_up",
            "job_recruiter_follow_up",
        ])
        self.assertEqual(actions[0]["priority"], "critical")
        self.assertEqual(actions[0]["days_until_due"], -2)
        self.assertEqual(actions[1]["priority"], "high")
        self.assertEqual(count_job_actions(actions), {
            "overdue": 1,
            "due_today": 0,
            "upcoming": 1,
            "total": 2,
        })

    def test_excludes_distant_invalid_and_inactive_follow_ups(self):
        actions = build_job_actions(
            [
                {"id": "rejected", "status": "rejected", "follow_up_date": "2026-08-10"},
                {"id": "distant", "status": "applied", "follow_up_date": "2026-09-30"},
                {"id": "invalid", "status": "applied", "follow_up_date": "not-a-date"},
            ],
            [{"id": "inactive", "connection_status": "inactive", "follow_up_date": "2026-08-11"}],
            today=date(2026, 8, 11),
        )

        self.assertEqual(actions, [])

    def test_due_today_action_is_critical(self):
        actions = build_job_actions(
            [{
                "id": "application-1",
                "job_title": "Shift Supervisor",
                "company_name": "Packaging Co",
                "status": "interview",
                "follow_up_date": "2026-08-11",
            }],
            [],
            today=date(2026, 8, 11),
        )

        self.assertEqual(actions[0]["priority"], "critical")
        self.assertEqual(actions[0]["days_until_due"], 0)

    def test_application_stage_maps_to_company_pipeline(self):
        self.assertEqual(company_target_status("saved"), "targeting")
        self.assertEqual(company_target_status("interview"), "interview")
        self.assertEqual(company_target_status("offer"), "offer")
        self.assertEqual(company_target_status("visa"), "offer")
        self.assertEqual(company_target_status("rejected"), "paused")


if __name__ == "__main__":
    unittest.main()
