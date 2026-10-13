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

    def test_new_cdn_and_required_ui(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('cdn.yigeyao.com', html)
        self.assertNotIn('cdn.jia.nz', html)
        for value in ('id="net-domestic"', 'id="net-foreign"', 'id="net-cloudflare"',
                      'id="net-google"', 'id="net-dns"', 'id="dns-grid"',
                      'id="rows"', 'id="top-grid"', 'id="count-ct"',
                      'href="./assets/network.css?v=2"', 'src="./assets/network.js?v=2"'):
            self.assertIn(value, html)
        self.assertTrue((ROOT / "assets/network.js").is_file())
        self.assertTrue((ROOT / "assets/network.css").is_file())

    def test_no_simulated_latency_or_ip(self):
        script = (ROOT / "assets/network.js").read_text(encoding="utf-8")
        self.assertIn('performance.now()', script)
        self.assertIn('net-google', script)
        self.assertIn('myip.ipip.net/json', script)
        self.assertIn('speed.cloudflare.com/meta', script)
        self.assertNotIn('cdn.jia.nz', script)


if __name__ == "__main__":
    unittest.main()
