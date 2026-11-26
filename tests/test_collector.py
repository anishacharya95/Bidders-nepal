import unittest
from datetime import datetime, timezone

from app.collector import _allowed, _canonical_url, _category, _deadline, _looks_like_notice, _notice_number


class CollectorParsingTests(unittest.TestCase):
    def test_only_approved_https_hosts_are_allowed(self):
        self.assertTrue(_allowed("https://ppmo.gov.np/notices"))
        self.assertFalse(_allowed("http://ppmo.gov.np/notices"))
        self.assertFalse(_allowed("https://example.com/notices"))

    def test_url_normalization_removes_fragment_and_trailing_slash(self):
        self.assertEqual(
            _canonical_url("https://PPMO.gov.np/a/b/?x=1#section"),
            "https://ppmo.gov.np/a/b?x=1",
        )

    def test_notice_detection_ignores_navigation_links(self):
        self.assertTrue(_looks_like_notice("Invitation for Bid - Road", "/bid-notice/123"))
        self.assertFalse(_looks_like_notice("Contact us", "/contact"))

    def test_notice_number_extraction(self):
        self.assertEqual(_notice_number("IFB 04/2083/84 Road Construction"), "IFB 04/2083/84 Road Construction")

    def test_category_classification_is_conservative(self):
        self.assertEqual(_category("Construction of rural road works"), "Works")
        self.assertEqual(_category("Supply of medical goods"), "Goods")
        self.assertEqual(_category("General notice"), "Other")

    def test_iso_deadline_is_parsed_as_utc(self):
        self.assertEqual(
            _deadline("Submission deadline: 2026-12-15"),
            datetime(2026, 12, 15, tzinfo=timezone.utc),
        )


if __name__ == "__main__":
    unittest.main()
