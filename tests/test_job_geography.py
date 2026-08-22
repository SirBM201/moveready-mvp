import unittest

from app.services import job_geography as geo


class JobGeographyTests(unittest.TestCase):
    def test_common_country_aliases_normalize_globally(self):
        cases = {
            "CA": "Canada",
            "USA": "United States",
            "UK": "United Kingdom",
            "DE": "Germany",
            "FR": "France",
            "NL": "Netherlands",
            "PT": "Portugal",
            "FI": "Finland",
            "AE": "United Arab Emirates",
            "UAE": "United Arab Emirates",
            "KW": "Kuwait",
            "SA": "Saudi Arabia",
            "NG": "Nigeria",
            "GH": "Ghana",
            "KE": "Kenya",
            "ZA": "South Africa",
            "BR": "Brazil",
            "MX": "Mexico",
            "IN": "India",
            "SG": "Singapore",
            "JP": "Japan",
            "KR": "South Korea",
            "AU": "Australia",
            "NZ": "New Zealand",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(geo.normalize_country(raw), expected)

    def test_unknown_country_is_preserved_not_relabelled(self):
        self.assertEqual(geo.normalize_country("Example Republic"), "Example Republic")

    def test_infer_location_handles_representative_regions(self):
        cases = [
            (["Toronto, Ontario, Canada"], ("Canada", "Ontario", "Toronto")),
            (["Munich, Germany"], ("Germany", None, "Munich")),
            (["Lagos, Nigeria"], ("Nigeria", None, "Lagos")),
            (["Sao Paulo, Brazil"], ("Brazil", None, "Sao Paulo")),
            (["Dubai, UAE"], ("United Arab Emirates", None, "Dubai")),
            (["Singapore, SG"], ("Singapore", None, "Singapore")),
            (["Sydney, Australia"], ("Australia", None, "Sydney")),
            (["Auckland, New Zealand"], ("New Zealand", None, "Auckland")),
            (["Lisbon, Portugal"], ("Portugal", None, "Lisbon")),
            (["Helsinki, Finland"], ("Finland", None, "Helsinki")),
        ]
        for values, expected in cases:
            with self.subTest(values=values):
                self.assertEqual(geo.infer_location(values), expected)

    def test_country_matching_is_profile_filter_not_discovery_rule(self):
        candidate = {"country": "Brazil"}
        self.assertTrue(geo.country_matches(candidate, "Brazil"))
        self.assertTrue(geo.country_matches(candidate, "BR"))
        self.assertFalse(geo.country_matches(candidate, "Canada"))
        self.assertTrue(geo.country_matches(candidate, ""))


if __name__ == "__main__":
    unittest.main()
