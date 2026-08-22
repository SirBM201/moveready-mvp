import unittest

from app.services import job_ats_extensions as ats
from app.services import job_discovery as discovery


GUPY_HTML = '''
<html><head>
<script type="application/ld+json">
{
  "@context":"https://schema.org",
  "@type":"JobPosting",
  "title":"Process Technician",
  "description":"Operate and improve injection molding production processes.",
  "datePosted":"2026-08-20T00:00:00Z",
  "hiringOrganization":{"@type":"Organization","name":"Example Packaging"},
  "jobLocation":{"@type":"Place","address":{"@type":"PostalAddress","addressLocality":"Sao Paulo","addressRegion":"SP","addressCountry":"BRA"}},
  "url":"https://example.gupy.io/jobs/123"
}
</script>
</head><body></body></html>
'''


class JobAtsExtensionTests(unittest.TestCase):
    def setUp(self):
        ats.install()

    def test_gupy_host_is_supported(self):
        self.assertTrue(ats.is_gupy_url("https://example.gupy.io/"))
        self.assertTrue(discovery.source_host_is_allowed("https://example.gupy.io/jobs", []))
        self.assertEqual(discovery.detect_adapter("https://example.gupy.io/", "auto"), "gupy")

    def test_public_gupy_jsonld_preserves_global_location(self):
        parsed = discovery.parse_source(
            GUPY_HTML,
            content_type="text/html",
            source_url="https://example.gupy.io/",
            adapter="gupy",
            keywords=["Process Technician"],
        )
        self.assertEqual(parsed["adapter"], "gupy")
        self.assertEqual(len(parsed["jobs"]), 1)
        job = parsed["jobs"][0]
        self.assertEqual(job["country"], "Brazil")
        self.assertEqual(job["city"], "Sao Paulo")
        self.assertEqual(job["source_name"], "Official Gupy employer career page")

    def test_gupy_parser_respects_role_keywords(self):
        parsed = discovery.parse_source(
            GUPY_HTML,
            content_type="text/html",
            source_url="https://example.gupy.io/",
            adapter="gupy",
            keywords=["Finance Director"],
        )
        self.assertEqual(parsed["jobs"], [])


if __name__ == "__main__":
    unittest.main()
