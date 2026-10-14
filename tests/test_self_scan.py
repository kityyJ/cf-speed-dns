import ipaddress
import unittest
from unittest.mock import Mock, patch

from self_scan import (
    IP_RANGES_URL, check_ip, official_networks, rank_ips, select_ips, validate_hosts,
)


NETS = [ipaddress.ip_network("104.16.0.0/13"),
        ipaddress.ip_network("172.64.0.0/13")]


class SelfScanTests(unittest.TestCase):
    def test_reads_official_cloudflare_cidrs(self):
        session = Mock()
        session.get.return_value.text = "\n".join(
            str(ipaddress.ip_network(f"104.{16+i}.0.0/16")) for i in range(12))
        networks = official_networks(session)
        self.assertEqual(len(networks), 12)
        session.get.assert_called_once_with(IP_RANGES_URL, timeout=15)

    def test_rejects_nonofficial_or_incomplete_prefix_lists(self):
        session = Mock()
        session.get.return_value.text = "10.0.0.0/8\n"
        with self.assertRaises(ValueError):
            official_networks(session)

    def test_sample_only_public_official_prefixes(self):
        a = select_ips(NETS, 5, "first")
        b = select_ips(NETS, 5, "second")
        self.assertEqual(len(a), 10)
        self.assertNotEqual(a, b)
        self.assertEqual(a, select_ips(NETS, 5, "first"))
        self.assertTrue(all(any(ipaddress.ip_address(ip) in n for n in NETS) for ip in a))

    def test_rejects_injected_or_non_dns_hostnames(self):
        self.assertEqual(validate_hosts(["WWW.Example.Com", "www.example.com"]),
                         ["www.example.com"])
        for name in ("http://foo.com", "foo.com\r\nHost: x", "../a", "localhost"):
            with self.assertRaises(ValueError):
                validate_hosts([name])

    def test_all_sites_must_be_https_compatible(self):
        with patch("self_scan.site_check") as check:
            check.side_effect = [
                {"ok": True, "status": 200, "ttfb_ms": 40, "total_ms": 100},
                {"ok": False, "status": 403},
            ]
            record = check_ip("104.16.0.1", ["a.example.com", "b.example.com"], 1)
        self.assertFalse(record["ok"])
        self.assertEqual(len(record["checks"]), 2)

    def test_measured_latency_uses_median_of_real_checks(self):
        with patch("self_scan.site_check") as check:
            check.side_effect = [
                {"ok": True, "status": 200, "ttfb_ms": 40, "total_ms": 100},
                {"ok": True, "status": 200, "ttfb_ms": 60, "total_ms": 150},
            ]
            record = check_ip("104.16.0.2", ["a.example.com", "b.example.com"], 1)
        self.assertTrue(record["ok"])
        self.assertEqual(record["ttfb_ms"], 50)
        self.assertEqual(record["total_ms"], 125)

    def test_failed_candidates_not_selected(self):
        def outcome(ip, hosts, timeout):
            if ip.endswith(".1"):
                return {"ip": ip, "ok": False, "checks": {}}
            return {"ip": ip, "ok": True, "ttfb_ms": 90, "total_ms": 110, "checks": {}}
        with patch("self_scan.select_ips", return_value=["104.16.0.1", "104.16.0.2"]), \
             patch("self_scan.check_ip", side_effect=outcome):
            scanned, passed = rank_ips(NETS, ["a.example.com"], 1, "test", 1, 1)
        self.assertEqual(len(scanned), 2)
        self.assertEqual([r["ip"] for r in passed], ["104.16.0.2"])


if __name__ == "__main__":
    unittest.main()
