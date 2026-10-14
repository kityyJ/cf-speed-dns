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

    def test_latency_column_and_compact_header(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('class="header-summary"', html)
        self.assertIn('id="updated"', html)
        self.assertNotIn('<section class="title-section">', html)
        self.assertIn('来源延迟仅供参考，非实时测速', html)
        self.assertIn('reportedLatency(tag)', html)
        self.assertIn('colspan="8"', html)
        self.assertIn('延迟 ⓘ', html)

    def test_latency_first_sort_and_missing_data_disclosure(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('来源延迟 ⓘ', html)
        self.assertIn('latencyMs!==null', html)
        self.assertIn('有来源延迟', html)
        self.assertIn('上游没有提供延迟', html)
        self.assertIn('latency_ms:r.latencyMs', html)
        self.assertIn('data-filter="dns"', html)

    def test_page_is_display_only_change(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("DNS 只读查询，不修改后台记录", html)
        self.assertNotIn("speed.cloudflare.com", html)
        self.assertNotIn("myip.ipip.net", html)


    def test_fixed_ten_item_pagination_and_mobile_cards(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("const pageSize=10;", html)
        self.assertIn("每页最多 ${pageSize} 条", html)
        self.assertIn("Math.ceil(rows.length/pageSize)", html)
        self.assertIn("Math.min(start+pageSize,rows.length)", html)
        self.assertIn("function filtered()", html)
        self.assertIn("function download(type){const rows=filtered()", html)
        self.assertIn('id="export-json"', html)
        self.assertIn('id="prev-page"', html)
        self.assertIn('id="next-page"', html)
        self.assertIn('aria-label="上一页"', html)
        self.assertIn('aria-label="下一页"', html)
        self.assertNotIn('<span>上一页</span>', html)
        self.assertNotIn('<span>下一页</span>', html)
        self.assertNotIn('title="上一页"', html)
        self.assertNotIn('title="下一页"', html)
        self.assertIn("morphicons@1.7.1/dom", html)
        self.assertIn("createMorph(path, icon.from)", html)
        self.assertIn("morph.morphTo(active ? icon.to : icon.from", html)
        self.assertIn(".page-btn{display:inline-flex;", html)
        self.assertIn("white-space:nowrap;background:var(--panel)", html)
        self.assertNotIn("calculatePageSize", html)
        self.assertIn("grid-template-areas:", html)
        self.assertIn("@media(max-width:920px)", html)
        self.assertIn("@media(min-width:680px) and (max-width:920px)", html)
        self.assertIn("@media(max-width:650px)", html)

if __name__ == "__main__":
    unittest.main()
