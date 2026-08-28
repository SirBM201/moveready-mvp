import unittest
from unittest.mock import patch
import httpx
from app.services import job_discovery_hardening as hardening


class JobDiscoveryHardeningTests(unittest.TestCase):
    def test_related_industrial_titles_require_description_evidence(self):
        terms = ["Production Supervisor", "Production Supervision", "Shift Leadership", "Production Planning"]
        for title in ["Compounder", "Millwright (433A Licensed)", "Moulds Coordinator - Contract"]:
            row = {"job_title": title, "description_summary": "Support manufacturing and production equipment."}
            self.assertTrue(hardening._candidate_is_relevant(row, terms))
            self.assertFalse(hardening._candidate_is_relevant({"job_title": title}, terms))
        for title in ["Assistant Manager", "Financial Analyst", "DevOps Engineer"]:
            self.assertFalse(hardening._candidate_is_relevant({"job_title": title, "description_summary": "Leadership and planning for a manufacturing company."}, terms))

    def test_filter_diagnostics_do_not_mark_filtered_feed_complete(self):
        rows = [
            {"job_title": "Moulds Coordinator", "job_url": "https://example.com/jobs/1", "country": "Canada", "description_summary": "Manufacturing production support"},
            {"job_title": "Retail Manager", "job_url": "https://example.com/jobs/2", "country": "Canada"},
        ]
        with patch.object(hardening, "_ORIGINAL_FETCH_SOURCE", return_value={"adapter":"greenhouse", "jobs":rows, "complete_listing":True}) as fetch:
            result = hardening.fetch_source_hardened("https://boards.greenhouse.io/example", "auto", ["Production Supervisor"])
        self.assertEqual(fetch.call_args.args[2], [])
        self.assertEqual(result["diagnostics"]["extracted"], 2)
        self.assertEqual(result["diagnostics"]["after_relevance"], 1)
        self.assertFalse(result["complete_listing"])

    def test_description_evidence_is_not_truncated_to_title_length(self):
        row = {"job_title": "Moulds Coordinator", "description_summary": "Benefits and introduction. " * 20 + "Support production machinery."}
        self.assertTrue(hardening._candidate_is_relevant(row, ["Production Supervisor"]))

    def test_greenhouse_office_address_supplies_country_without_guessing(self):
        import json
        from app.services import job_discovery
        def parse(offices):
            return job_discovery._parse_greenhouse(json.dumps({"jobs":[{"title":"Compounder", "location":{"name":"Toronto"}, "offices":offices}]}), "https://boards.greenhouse.io/example")[0]
        self.assertEqual(parse([{"location":"Toronto, Ontario, Canada"}])["country"], "Canada")
        self.assertIsNone(parse([])["country"])
        self.assertIsNone(parse([{"location":"Canada"},{"location":"United States"}])["country"])

    def test_navigation_links_are_not_vacancies(self):
        self.assertFalse(hardening._looks_like_real_vacancy({"job_title": "Search jobs", "job_url": "https://example.com/jobs"}))
        self.assertTrue(hardening._looks_like_real_vacancy({"job_title": "Production Supervisor", "job_url": "https://example.com/jobs/123", "country": "Canada"}))

    def test_real_vacancy_is_not_canada_dependent(self):
        for country, city in [("Brazil", "Sao Paulo"), ("Germany", "Munich"), ("Nigeria", "Lagos")]:
            with self.subTest(country=country):
                self.assertTrue(hardening._looks_like_real_vacancy({
                    "job_title": "Injection Molding Technician",
                    "job_url": f"https://example.com/{country.casefold()}/jobs/123",
                    "country": country,
                    "city": city,
                }))

    def test_duplicate_tracking_urls_collapse(self):
        rows = [
            {"job_title": "Assembly Technician (Contract)", "job_url": "https://example.com/jobs/123?src=a", "company_name": "Husky Technologies", "country": "Canada", "city": "Bolton"},
            {"job_title": "Assembly Technician (Contract)", "job_url": "https://example.com/jobs/123?src=b", "company_name": "Husky Technologies", "country": "Canada", "city": "Bolton"},
        ]
        merged = hardening._merge_jobs([rows], ["Assembly Technician"])
        self.assertEqual(len(merged), 1)

    def test_same_role_in_different_countries_is_not_deduplicated(self):
        rows = [
            {"job_title": "Production Supervisor", "job_url": "https://example.com/jobs/ca-123", "company_name": "Example Plastics", "country": "Canada", "city": "Toronto"},
            {"job_title": "Production Supervisor", "job_url": "https://example.com/jobs/br-123", "company_name": "Example Plastics", "country": "Brazil", "city": "Sao Paulo"},
            {"job_title": "Production Supervisor", "job_url": "https://example.com/jobs/de-123", "company_name": "Example Plastics", "country": "Germany", "city": "Munich"},
        ]
        merged = hardening._merge_jobs([rows], ["Production Supervisor"])
        self.assertEqual(len(merged), 3)
        self.assertEqual({row["country"] for row in merged}, {"Canada", "Brazil", "Germany"})

    def test_country_metadata_is_preserved(self):
        row = {"job_title": "Process Technician", "job_url": "https://example.com/jobs/77", "company_name": "Example", "country": "Brazil", "city": "Curitiba"}
        merged = hardening._merge_jobs([[row]], ["Process Technician"])
        self.assertEqual(merged[0]["country"], "Brazil")
        self.assertEqual(merged[0]["city"], "Curitiba")

    def test_generic_single_token_false_positive_is_rejected(self):
        row = {"job_title": "Manufacturing Engineer (Contract)", "job_url": "https://example.com/jobs/9", "country": "Canada"}
        self.assertFalse(hardening._candidate_is_relevant(row, ["Production Supervisor", "Manufacturing Supervisor", "Team Leader", "Injection Molding Technician"]))

    def test_distinctive_target_role_is_kept(self):
        row = {"job_title": "Injection Molding Process Technician", "job_url": "https://example.com/jobs/10", "country": "Brazil"}
        self.assertTrue(hardening._candidate_is_relevant(row, ["Injection Molding Technician"]))

    def test_generic_pages_are_paginated_and_deduplicated_across_countries(self):
        first = {"adapter": "generic", "jobs": [{"job_title": "Production Supervisor", "job_url": "https://example.com/jobs/1", "country": "Canada"}], "fetched_url": "https://example.com/careers", "complete_listing": False}
        second = {"adapter": "generic", "jobs": [{"job_title": "Injection Molding Technician", "job_url": "https://example.com/jobs/2", "country": "Brazil"}], "fetched_url": "https://example.com/careers?page=1", "complete_listing": False}
        duplicate = {"adapter": "generic", "jobs": list(second["jobs"]), "fetched_url": "https://example.com/careers?page=2", "complete_listing": False}
        with patch.object(hardening, "_ORIGINAL_FETCH_SOURCE", side_effect=[first, second, duplicate]):
            result = hardening.fetch_source_hardened("https://example.com/careers", "auto", ["Production Supervisor", "Injection Molding Technician"])
        self.assertEqual(len(result["jobs"]), 2)
        self.assertEqual({row["country"] for row in result["jobs"]}, {"Canada", "Brazil"})
        self.assertEqual(result["pagination_pages_checked"], 3)
        self.assertFalse(result["complete_listing"])

    def test_optional_pagination_failure_does_not_fail_working_first_page(self):
        first = {"adapter": "generic", "jobs": [{"job_title": "Manufacturing Technician", "job_url": "https://example.com/jobs/1", "country": "Germany"}], "fetched_url": "https://example.com/careers", "complete_listing": False}
        with patch.object(hardening, "_ORIGINAL_FETCH_SOURCE", side_effect=[first, RuntimeError("page unsupported")]):
            result = hardening.fetch_source_hardened("https://example.com/careers", "auto", ["Manufacturing Technician"])
        self.assertEqual(len(result["jobs"]), 1)
        self.assertEqual(result["jobs"][0]["country"], "Germany")
        self.assertEqual(result["pagination_pages_checked"], 1)

    def test_transient_timeout_is_retried_and_recovers(self):
        success = {"adapter": "greenhouse", "jobs": [], "complete_listing": True, "http_status": 200}
        with patch.object(hardening, "_ORIGINAL_FETCH_SOURCE", side_effect=[httpx.ReadTimeout("slow source"), success]), patch.object(hardening.time, "sleep"):
            result = hardening.fetch_source_hardened("https://boards.greenhouse.io/example", "auto", [])
        self.assertEqual(result["fetch_attempts"], 2)
        self.assertTrue(result["recovered_after_retry"])

    def test_503_is_retried_but_403_is_not(self):
        request = httpx.Request("GET", "https://example.com/careers")
        err503 = httpx.HTTPStatusError("503", request=request, response=httpx.Response(503, request=request))
        err403 = httpx.HTTPStatusError("403", request=request, response=httpx.Response(403, request=request))
        success = {"adapter": "generic", "jobs": [], "complete_listing": False, "http_status": 200}
        with patch.object(hardening, "_ORIGINAL_FETCH_SOURCE", side_effect=[err503, success]), patch.object(hardening.time, "sleep"):
            result = hardening.fetch_source_hardened("https://example.com/careers", "auto", [])
        self.assertEqual(result["fetch_attempts"], 2)
        with patch.object(hardening, "_ORIGINAL_FETCH_SOURCE", side_effect=err403) as fetch:
            with self.assertRaisesRegex(RuntimeError, "official_source_access_blocked_http_403"):
                hardening.fetch_source_hardened("https://example.com/careers", "auto", [])
        self.assertEqual(fetch.call_count, 1)


if __name__ == "__main__":
    unittest.main()
