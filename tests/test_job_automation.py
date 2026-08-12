import unittest

from app.services.job_discovery import (
    adapter_request_url,
    candidate_matches_target_country,
    candidate_content_hash,
    candidate_fingerprint,
    parse_source,
    source_host_is_allowed,
    validate_public_https_url,
)
from app.services import job_discovery
from app.services.job_documents import approval_confirmations_are_complete, build_application_drafts


class JobAutomationDiscoveryTests(unittest.TestCase):
    def test_jsonld_job_is_filtered_and_normalized(self):
        body = """
        <html><script type="application/ld+json">
        {
          "@context":"https://schema.org",
          "@type":"JobPosting",
          "title":"Production Supervisor",
          "url":"https://plastics.example/jobs/production-supervisor",
          "description":"Lead PET injection moulding production and train operators.",
          "datePosted":"2026-08-12",
          "jobLocation":{"address":{"addressCountry":"CA","addressRegion":"Ontario","addressLocality":"Toronto"}}
        }
        </script></html>
        """
        result = parse_source(
            body,
            content_type="text/html",
            source_url="https://plastics.example/careers",
            adapter="jsonld",
            keywords=["Production Supervisor", "PET preforms"],
        )
        self.assertEqual(len(result["jobs"]), 1)
        job = result["jobs"][0]
        self.assertEqual(job["job_title"], "Production Supervisor")
        self.assertEqual(job["province"], "Ontario")
        self.assertEqual(job["country"], "Canada")
        self.assertTrue(candidate_fingerprint(job, "watch-1"))
        self.assertTrue(candidate_content_hash(job))

    def test_unrelated_job_is_not_returned(self):
        body = '<script type="application/ld+json">{"@type":"JobPosting","title":"Accountant","url":"https://example.com/jobs/1"}</script>'
        result = parse_source(
            body,
            content_type="text/html",
            source_url="https://example.com/careers",
            adapter="jsonld",
            keywords=["Injection moulding", "Production Supervisor"],
        )
        self.assertEqual(result["jobs"], [])

    def test_source_policy_allows_employer_and_supported_ats_only(self):
        company_urls = ["https://www.example.com/careers"]
        self.assertTrue(source_host_is_allowed("https://jobs.example.com/openings", company_urls))
        self.assertTrue(source_host_is_allowed("https://jobs.lever.co/example", company_urls))
        self.assertFalse(source_host_is_allowed("https://unrelated.example/jobs", company_urls))
        self.assertEqual(
            validate_public_https_url("https://example.com/jobs", resolve_dns=False),
            "https://example.com/jobs",
        )
        with self.assertRaises(ValueError):
            validate_public_https_url("http://example.com/jobs", resolve_dns=False)
        with self.assertRaises(ValueError):
            validate_public_https_url("https://127.0.0.1/jobs", resolve_dns=False)

    def test_workday_public_feed_is_normalized(self):
        body = '{"jobPostings":[{"title":"Injection Moulding Supervisor","externalPath":"/job/Ontario/Injection-Moulding-Supervisor_R123","locationsText":"Ontario, Canada","postedOn":"Posted Today"}]}'
        result = parse_source(
            body,
            content_type="application/json",
            source_url="https://example.wd1.myworkdayjobs.com/Example_Careers",
            adapter="workday",
            keywords=["Injection moulding"],
        )
        self.assertEqual(len(result["jobs"]), 1)
        self.assertEqual(result["jobs"][0]["source_name"], "Official Workday career site")
        self.assertEqual(result["jobs"][0]["country"], "Canada")
        self.assertEqual(result["jobs"][0]["province"], "Ontario")
        self.assertIn("/Example_Careers/job/", result["jobs"][0]["job_url"])
        self.assertTrue(result["complete_listing"])
        self.assertEqual(
            adapter_request_url("https://example.wd1.myworkdayjobs.com/en-US/Example_Careers", "workday"),
            "https://example.wd1.myworkdayjobs.com/wday/cxs/example/Example_Careers/jobs",
        )

    def test_corporate_page_can_identify_supported_ats_link(self):
        body = '<a href="https://example.wd1.myworkdayjobs.com/Example_Careers">Search current opportunities</a>'
        link = job_discovery._discover_supported_ats_link(body, "https://www.example.com/careers")
        self.assertEqual(link, "https://example.wd1.myworkdayjobs.com/Example_Careers")

    def test_official_listing_link_is_followed_without_leaving_employer_domain(self):
        body = '<a href="/careers/job-search">Search open jobs</a><a href="https://unrelated.example/jobs">Jobs elsewhere</a>'
        link = job_discovery._discover_official_listing_link(body, "https://www.example.com/careers")
        self.assertEqual(link, "https://www.example.com/careers/job-search")

    def test_generic_table_locations_are_not_relabelled_as_canada(self):
        body = """
        <table>
          <tr><td><a href="/jobs/1">Production Supervisor</a></td><td>Employer Inc</td><td>United States of America</td><td>Kansas City</td></tr>
          <tr><td><a href="/jobs/2">Injection Moulding Lead</a></td><td>Bolton, ON</td><td>21105</td></tr>
        </table>
        """
        result = parse_source(
            body,
            content_type="text/html",
            source_url="https://example.com/careers/portal",
            adapter="generic",
            keywords=["Production Supervisor", "Injection Moulding"],
        )
        self.assertEqual(len(result["jobs"]), 2)
        by_title = {row["job_title"]: row for row in result["jobs"]}
        self.assertEqual(by_title["Production Supervisor"]["country"], "United States")
        self.assertFalse(candidate_matches_target_country(by_title["Production Supervisor"], "Canada"))
        self.assertEqual(by_title["Injection Moulding Lead"]["country"], "Canada")
        self.assertEqual(by_title["Injection Moulding Lead"]["province"], "Ontario")
        self.assertTrue(candidate_matches_target_country(by_title["Injection Moulding Lead"], "Canada"))

    def test_target_country_requires_source_location_evidence(self):
        self.assertFalse(candidate_matches_target_country({"job_title": "Production Lead"}, "Canada"))
        self.assertTrue(candidate_matches_target_country({"country": "Canada"}, "Canada"))


class JobAutomationDocumentTests(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "display_name": "Moses",
            "headline": "Production Supervisor and PET Injection Moulding Specialist",
            "years_experience": 19,
            "education_level": "OND Mechanical Engineering Technology",
            "current_employer": "Genoa Plastic Industries",
            "previous_employer": "Sonnex Packaging",
            "skills": ["PET preforms", "Injection moulding", "Operator training"],
            "career_facts": ["Reduced a documented process delay by 15 percent."],
            "work_authorization_status": "requires_sponsorship",
        }
        self.job = {
            "job_title": "Production Supervisor",
            "country": "Canada",
            "province": "Ontario",
            "description_summary": "Lead injection moulding production and train operators.",
            "job_url": "https://example.com/jobs/1",
            "skills": ["Injection moulding", "Leadership"],
        }

    def test_drafts_use_only_recorded_profile_and_resume_evidence(self):
        drafts = build_application_drafts(
            profile=self.profile,
            job=self.job,
            company_name="Example Plastics",
            resume_asset_id="resume-1",
            resume_text="Reduced a documented process delay by 15 percent. Trained production operators.",
        )
        self.assertEqual({item["draft_type"] for item in drafts}, {"tailored_resume", "cover_letter"})
        for draft in drafts:
            self.assertEqual(draft["generation_method"], "verified_template")
            self.assertGreater(draft["truth_basis"]["verified_fact_count"], 0)
            self.assertIn("requires sponsorship", draft["content"])
            self.assertNotIn("guaranteed sponsorship", draft["content"].lower())

    def test_all_four_truth_confirmations_are_required(self):
        complete = {
            "facts_verified": True,
            "no_invented_claims": True,
            "contact_details_checked": True,
            "work_authorization_checked": True,
        }
        self.assertTrue(approval_confirmations_are_complete(complete))
        self.assertFalse(approval_confirmations_are_complete({**complete, "facts_verified": False}))


if __name__ == "__main__":
    unittest.main()
