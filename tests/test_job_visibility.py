import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "job_visibility.py"
SPEC = importlib.util.spec_from_file_location("job_visibility", MODULE_PATH)
assert SPEC and SPEC.loader
JOB_VISIBILITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(JOB_VISIBILITY)
job_is_visible_to_account = JOB_VISIBILITY.job_is_visible_to_account


class JobVisibilityTests(unittest.TestCase):
    def test_curated_job_is_visible_for_application_tracking(self):
        self.assertTrue(job_is_visible_to_account({
            "id": "job-1",
            "is_curated": True,
            "owner_email": None,
        }, "person@example.com"))

    def test_private_job_is_visible_only_to_its_owner(self):
        row = {"id": "job-1", "is_curated": False, "owner_email": "Person@Example.com"}
        self.assertTrue(job_is_visible_to_account(row, "person@example.com"))
        self.assertFalse(job_is_visible_to_account(row, "someone-else@example.com"))

    def test_missing_job_is_not_visible(self):
        self.assertFalse(job_is_visible_to_account(None, "person@example.com"))


if __name__ == "__main__":
    unittest.main()
