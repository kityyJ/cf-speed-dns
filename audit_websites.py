#!/usr/bin/env python3
"""Read-only audit of CDN DNS A records for real website HTTPS compatibility.

Run from GitHub Actions (not a mainland-China latency probe). No DNS writes.
"""
import concurrent.futures
import os
import sys
from collections import Counter

import requests

from dnscf import audit_site_https, dns_records


HOSTS = ("www.jia.nz", "cook.jia.nz")
CDN_NAME = "cdn.jia.nz"


def main():
    token = os.environ.get("CF_API_TOKEN")
    zone_id = os.environ.get("CF_ZONE_ID")
    if not token or not zone_id:
        print("Missing CF_API_TOKEN / CF_ZONE_ID (DNS read-only access required)")
        return 2

    with requests.Session() as session:
        records = dns_records(session, zone_id, CDN_NAME, token)
    ips = sorted({r["content"] for r in records if r.get("proxied") is False})
    if len(ips) != 30 or len(records) != 30:
        print(f"Unexpected {CDN_NAME} A pool: {len(records)} entries, {len(ips)} unique gray-cloud IPs")
        return 2

    print(f"Auditing {len(ips)} CDN IPs x {len(HOSTS)} HTTPS sites.")
    print("Values are measured from a GitHub runner, NOT from mainland China.")
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        jobs = {
            executor.submit(audit_site_https, ip, host, "/", 5.0): (host, ip)
            for host in HOSTS for ip in ips
        }
        for future in concurrent.futures.as_completed(jobs):
            host, ip = jobs[future]
            try:
                data = future.result()
            except Exception as exc:
                data = {"ip": ip, "ok": False, "error": type(exc).__name__}
            results[(host, ip)] = data

    failures = 0
    for host in HOSTS:
        good = sorted((v for (h, _), v in results.items() if h == host and v["ok"]),
                      key=lambda v: v["response_header_ms"])
        bad = sorted((v for (h, _), v in results.items() if h == host and not v["ok"]),
                     key=lambda v: v["ip"])
        failures += len(bad)
        metrics = [v["response_header_ms"] for v in good]
        if metrics:
            print(f"{host}: {len(good)}/{len(ips)} HTTPS valid, "
                  f"response-header time min={min(metrics):.0f}ms, "
                  f"median={sorted(metrics)[len(metrics) // 2]:.0f}ms, max={max(metrics):.0f}ms")
        else:
            print(f"{host}: 0/{len(ips)} HTTPS valid")
        for v in bad:
            print(f"  FAILED {host} {v['ip']}: {v.get('status', v.get('error'))}")
        print("  HTTP statuses:", dict(Counter(v.get("status", "network-error") for
                                           (h, _), v in results.items() if h == host)))

    print(f"All-site compatible IPs: "
          f"{sum(all(results[(host, ip)]['ok'] for host in HOSTS) for ip in ips)}/{len(ips)}")
    if failures:
        print("Some currently published IPs failed HTTPS checks; see details above.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
