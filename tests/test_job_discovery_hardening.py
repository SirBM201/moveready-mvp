import unittest
from unittest.mock import patch

from app.services import job_discovery_hardening as hardening


class JobDiscoveryHardeningTests(unittest.TestCase):
    def test_navigation_links_are_not_vacancies(self):
        self.assertFalse(hardening._looks_like_real_vacancy({
            "job_title": "Search jobs",
            "job_url": "https://example.com/jobs",
        }))
        self.assertTrue(hardening._looks_like_real_vacancy({
            "job_title": "Production Supervisor",
            "job_url": "https://example.com/jobs/123",
            "country": "Canada",
        }))

    def test_generic_pages_are_paginated_and_deduplicated(self):
        first = {
            "adapter": "generic",
            "jobs": [{
                "job_title": "Production Supervisor",
                "job_url": "https://example.com/jobs/1",
                "country": "Canada",
            }],
            "fetched_url": "https://example.com/careers",
            "complete_listing": False,
        }
        second = {
            "adapter": "generic",
            "jobs": [{
                "job_title": "Injection Molding Technician",
                "job_url": "https://example.com/jobs/2",
                "country": "Canada",
            }],
            "fetched_url": "https://example.com/careers?page=1",
            "complete_listing": False,
        }
        duplicate = {
            "adapter": "generic",
            "jobs": list(second["jobs"]),
            "fetched_url": "https://example.com/careers?page=2",
            "complete_listing": False,
        }
        with patch.object(hardening, "_ORIGINAL_FETCH_SOURCE", side_effect=[first, second, duplicate]):
            result = hardening.fetch_source_hardened(
                "https://example.com/careers", "auto", ["Production Supervisor", "Injection Molding"]
            )
        self.assertEqual(len(result["jobs"]), 2)
        self.assertEqual(result["pagination_pages_checked"], 3)
        self.assertFalse(result["complete_listing"])

    def test_optional_pagination_failure_does_not_fail_working_first_page(self):
        first = {
            "adapter": "generic",
            "jobs": [{
                "job_title": "Manufacturing Technician",
                "job_url": "https://example.com/jobs/1",
                "country": "Canada",
            }],
            "fetched_url": "https://example.com/careers",
            "complete_listing": False,
        }
        with patch.object(hardening, "_ORIGINAL_FETCH_SOURCE", side_effect=[first, RuntimeError("page unsupported")]):
            result = hardening.fetch_source_hardened(
                "https://example.com/careers", "auto", ["Manufacturing Technician"]
            )
        self.assertEqual(len(result["jobs"]), 1)
        self.assertEqual(result["pagination_pages_checked"], 1)


if __name__ == "__main__":
    unittest.main()
