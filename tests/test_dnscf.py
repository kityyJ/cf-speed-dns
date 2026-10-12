import ipaddress
import unittest

from dnscf import DnsSyncError, dns_records, pick_ips, sync_dns

NETWORKS = [ipaddress.ip_network("104.16.0.0/13"), ipaddress.ip_network("162.158.0.0/15")]


class FakeResponse:
    status_code = 200

    def __init__(self, result, success=True):
        self.data = {"success": success, "result": result}

    def json(self):
        return self.data


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def row(ip):
    return {"ip": ip, "port": 443}


class DNSTests(unittest.TestCase):
    def test_carrier_selection_and_reachability(self):
        pools = {
            "ct": [row("104.17.1.1"), row("104.17.1.2")],
            "cu": [row("104.17.1.2"), row("104.17.1.3")],
            "cmcc": [row("162.159.1.2")],
            "all": [row("1.1.1.1"), row("104.17.1.4")],
        }
        selected = pick_ips(pools, 3, NETWORKS, probe=lambda ip: ip != "104.17.1.1")
        self.assertEqual(selected, ["104.17.1.2", "104.17.1.3", "162.159.1.2"])

    def test_insufficient_ips_aborts(self):
        pools = {group: [] for group in ("ct", "cu", "cmcc", "all")}
        with self.assertRaises(DnsSyncError):
            pick_ips(pools, 3, NETWORKS)

    def test_exact_dns_pagination(self):
        sess = FakeSession([
            FakeResponse([{"id": "b", "name": "cdn.jia.nz", "type": "A", "content": "104.17.1.1"}]),
            FakeResponse([{"id": "a", "name": "cdn.jia.nz", "type": "A", "content": "104.17.1.2"}]),
        ])
        sess.responses[0].data["result_info"] = {"total_pages": 2}
        sess.responses[1].data["result_info"] = {"total_pages": 2}
        found = dns_records(sess, "zone", "cdn.jia.nz", "token")
        self.assertEqual([record["id"] for record in found], ["a", "b"])
        self.assertEqual(sess.calls[1][2]["params"]["page"], 2)

    def test_unchanged_records_are_not_shuffled(self):
        records = [
            {"id": "a", "content": "104.17.1.2", "proxied": False},
            {"id": "b", "content": "104.17.1.1", "proxied": False},
        ]
        sess = FakeSession([])
        self.assertEqual(sync_dns(sess, "zone", "cdn.jia.nz", "token", records,
                                  ["104.17.1.1", "104.17.1.2"]), [])
        self.assertFalse(sess.calls)

    def test_patch_only_changes_address(self):
        records = [{"id": "a", "content": "104.17.1.1", "proxied": False}]
        sess = FakeSession([FakeResponse({})])
        sync_dns(sess, "zone", "cdn.jia.nz", "token", records, ["104.17.1.2"])
        self.assertEqual(sess.calls[0][0], "PATCH")
        self.assertEqual(sess.calls[0][2]["json"], {"content": "104.17.1.2"})

    def test_cloudflare_rejects_update(self):
        records = [{"id": "a", "content": "104.17.1.1", "proxied": False}]
        with self.assertRaises(DnsSyncError):
            sync_dns(FakeSession([FakeResponse({}, False)]),
                     "zone", "cdn.jia.nz", "token", records, ["104.17.1.2"])

    def test_creates_missing_records(self):
        records = [{"id": "a", "content": "104.17.1.1", "proxied": False}]
        sess = FakeSession([FakeResponse({}), FakeResponse({})])
        changes = sync_dns(sess, "zone", "cdn.jia.nz", "token", records,
                           ["104.17.1.2", "104.17.1.3"])
        self.assertEqual(len(changes), 2)
        self.assertEqual([call[0] for call in sess.calls], ["PATCH", "POST"])
        self.assertEqual(sess.calls[1][2]["json"]["proxied"], False)
        self.assertEqual(sess.calls[1][2]["json"]["content"], "104.17.1.3")

    def test_sixty_carrier_balanced_candidates(self):
        ips = [f"104.17.{n // 250}.{n % 250 + 1}" for n in range(180)]
        pools = {
            "ct": [row(ip) for ip in ips[:60]],
            "cu": [row(ip) for ip in ips[60:120]],
            "cmcc": [row(ip) for ip in ips[120:180]],
            "all": [],
        }
        result = pick_ips(pools, 60, NETWORKS, probe=lambda ip: True)
        self.assertEqual(len(set(result)), 60)
        self.assertEqual(result[:3], [ips[0], ips[60], ips[120]])

    def test_proxy_mode_is_protected(self):
        records = [{"id": "a", "content": "104.17.1.1", "proxied": True}]
        with self.assertRaises(DnsSyncError):
            sync_dns(FakeSession([]), "zone", "cdn.jia.nz", "token", records, ["104.17.1.2"])


if __name__ == "__main__":
    unittest.main()
