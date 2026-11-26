import unittest
from datetime import datetime, timezone

from app.collector import _allowed, _canonical_url, _category, _deadline, _is_notice_detail_url, _looks_like_notice, _notice_number, _organization_from_title


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
        self.assertTrue(_looks_like_notice("Invitation for Bid - Road Construction"))
        self.assertTrue(_looks_like_notice("श्री भीम अस्पतालको पुनः दरभाउपत्र आह्वान सम्बन्धी सूचना"))
        self.assertTrue(_looks_like_notice("श्री कृष्णपुर नगरपालिका, नगर कार्यपालिकाको कार्यालय, कञ्चनपुरको दरभाउपत्र आह्वान सम्बन्धी सूचना"))
        self.assertTrue(_looks_like_notice("Invitation for Electronic Sealed Quotation"))
        self.assertFalse(_looks_like_notice("बोलपत्रदाता दर्ता प्रक्रिया पुस्तिका"))
        self.assertFalse(_looks_like_notice("विद्युतीय खरिद प्रणालीमा बोलपत्रको म्याद थप सम्बन्धी सूचना"))
        self.assertFalse(_looks_like_notice("Contact us", "/contact"))

    def test_only_individual_content_pages_are_candidate_urls(self):
        self.assertTrue(_is_notice_detail_url("https://ppmo.gov.np/content/13856/sample-notice/"))
        self.assertFalse(_is_notice_detail_url("https://ppmo.gov.np/category/1229/"))
        self.assertFalse(_is_notice_detail_url("https://ppmo.gov.np/"))

    def test_notice_number_extraction(self):
        self.assertEqual(_notice_number("IFB 04/2083/84 Road Construction"), "IFB 04/2083/84 Road Construction")

    def test_category_classification_is_conservative(self):
        self.assertEqual(_category("Construction of rural road works"), "Works")
        self.assertEqual(_category("Supply of medical goods"), "Goods")
        self.assertEqual(_category("General notice"), "Other")

    def test_organization_is_only_extracted_from_clear_nepali_title_prefix(self):
        self.assertEqual(
            _organization_from_title("श्री भीम अस्पताल, भैरहवा रुपन्देहीको पुनः दरभाउपत्र आह्वान सम्बन्धी सूचना"),
            "भीम अस्पताल, भैरहवा रुपन्देही",
        )
        self.assertEqual(
            _organization_from_title("Invitation for Bid - Road Construction"),
            "Not identified - admin review required",
        )

    def test_iso_deadline_is_parsed_as_utc(self):
        self.assertEqual(
            _deadline("Submission deadline: 2026-12-15"),
            datetime(2026, 12, 15, tzinfo=timezone.utc),
        )


if __name__ == "__main__":
    unittest.main()
