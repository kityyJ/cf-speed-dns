import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class FrontendTemplateTest(unittest.TestCase):
    def test_generator_matches_checked_in_html(self):
        generator = (ROOT / "aggregate_ips.py").read_text(encoding="utf-8")
        match = re.search(r'INDEX_HTML = r"""(.*?)\n"""', generator, re.S)
        self.assertIsNotNone(match)
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertEqual(match.group(1) + "\n", html)

    def test_compact_ip_table_keeps_existing_data_features(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("cdn.yigeyao.com", html)
        self.assertNotIn("cdn.jia.nz", html)
        for value in (
            'id="rows"', 'id="count-all"', 'id="count-dns"', 'id="count-ct"',
            'id="count-cu"', 'id="count-cmcc"', 'id="search"', 'id="refresh"',
            'id="copy-all"', 'id="export-txt"', 'id="export-json"',
            'data-filter="all"', 'data-filter="dns"', 'data-filter="ct"',
            'data-filter="cu"', 'data-filter="cmcc"',
            "./api/${g}.json", "./api/all.json", "./data/status.json"
        ):
            self.assertIn(value, html)

    def test_page_is_display_only_change(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("DNS 只读查询，不修改后台记录", html)
        self.assertNotIn("speed.cloudflare.com", html)
        self.assertNotIn("myip.ipip.net", html)

if __name__ == "__main__":
    unittest.main()
