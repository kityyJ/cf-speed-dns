#!/usr/bin/env python3
"""Independent HTTPS benchmark of OFFICIAL Cloudflare IPv4 address ranges.

No third-party preferred-IP feed. Results describe the runner's own network
only; a GitHub-hosted runner is NOT a China Telecom/Unicom/Mobile probe.
Read-only: this file never changes Cloudflare DNS.
"""
import argparse
import concurrent.futures
import datetime as dt
import http.client
import ipaddress
import json
import random
import re
import socket
import ssl
import statistics
import time
from pathlib import Path

import requests

IP_RANGES_URL = "https://www.cloudflare.com/ips-v4"


def official_networks(session):
    res = session.get(IP_RANGES_URL, timeout=15)
    res.raise_for_status()
    lines = [s.strip() for s in res.text.splitlines() if s.strip()]
    if not 10 <= len(lines) <= 100:
        raise ValueError("Official Cloudflare IP range list is incomplete")
    networks = [ipaddress.ip_network(x, strict=True) for x in lines]
    if (len(set(networks)) != len(networks)
            or any(n.version != 4 or not n.is_global for n in networks)):
        raise ValueError("Cloudflare IP range list contains invalid or duplicate prefixes")
    return networks


def select_ips(networks, count_per_prefix=12, seed="today"):
    if not 1 <= count_per_prefix <= 64:
        raise ValueError("count_per_prefix out of range")
    result = set()
    for net in networks:
        rng = random.Random(f"{seed}:{net}")
        start = 1 if net.num_addresses > 2 else 0
        end = net.num_addresses - 2 if net.num_addresses > 2 else net.num_addresses - 1
        for i in rng.sample(range(start, end + 1), min(count_per_prefix, end - start + 1)):
            result.add(str(net.network_address + i))
    return sorted(result, key=ipaddress.ip_address)


def validate_hosts(hosts):
    valid = []
    for host in hosts:
        host = host.strip().lower().rstrip(".")
        if (not 1 <= len(host) <= 253 or "." not in host
                or not re.fullmatch(r"[a-z0-9.-]+", host)
                or host.startswith("-") or host.endswith("-")
                or ".." in host or ".-" in host or "-." in host):
            raise ValueError("Invalid HTTPS hostname")
        if host not in valid:
            valid.append(host)
    if not 1 <= len(valid) <= 4:
        raise ValueError("Expected 1 to 4 HTTPS hostnames")
    return valid


def site_check(ip, host, timeout):
    t0 = time.monotonic()
    try:
        with socket.create_connection((ip, 443), timeout=timeout) as raw:
            t1 = time.monotonic()
            with ssl.create_default_context().wrap_socket(raw, server_hostname=host) as tls:
                t2 = time.monotonic()
                tls.settimeout(timeout)
                request = (
                    f"GET / HTTP/1.1\r\nHost: {host}\r\n"
                    "User-Agent: independent-cf-ip-scan/1.0\r\n"
                    "Accept-Encoding: identity\r\nConnection: close\r\n\r\n"
                )
                tls.sendall(request.encode("ascii"))
                response = http.client.HTTPResponse(tls)
                response.begin()
                t3 = time.monotonic()
                status = response.status
                content = response.read(16384)
                t4 = time.monotonic()
                response.close()
        return {
            "ok": 200 <= status < 400,
            "status": status,
            "tcp_ms": round((t1-t0)*1000, 1),
            "tls_ms": round((t2-t1)*1000, 1),
            "ttfb_ms": round((t3-t0)*1000, 1),
            "total_ms": round((t4-t0)*1000, 1),
            "body_bytes": len(content),
        }
    except (OSError, ValueError, http.client.HTTPException) as exc:
        return {"ok": False, "error": type(exc).__name__}


def check_ip(ip, hosts, timeout):
    checks = {}
    for host in hosts:
        outcome = site_check(ip, host, timeout)
        checks[host] = outcome
        if not outcome["ok"]:
            return {"ip": ip, "ok": False, "checks": checks}
    return {
        "ip": ip, "ok": True,
        "ttfb_ms": round(statistics.median(c["ttfb_ms"] for c in checks.values()), 1),
        "total_ms": round(statistics.median(c["total_ms"] for c in checks.values()), 1),
        "checks": checks,
    }


def rank_ips(networks, hosts, count_per_prefix, seed, workers, timeout):
    if not 1 <= workers <= 24:
        raise ValueError("workers out of range")
    ips = select_ips(networks, count_per_prefix=count_per_prefix, seed=seed)
    tested = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(check_ip, ip, hosts, timeout): ip for ip in ips}
        for future in concurrent.futures.as_completed(future_map):
            tested.append(future.result())
    passed = sorted((row for row in tested if row["ok"]),
                    key=lambda r: (r["total_ms"], r["ttfb_ms"], ipaddress.ip_address(r["ip"])))
    return ips, passed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hosts", required=True, help="Comma-separated website hostnames")
    parser.add_argument("--label", default="github-hosted", help="Truthful measurement network label")
    parser.add_argument("--per-prefix", type=int, default=12)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=3.5)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--output", default="data/self_scan_github.json")
    parser.add_argument("--api-json", default="api/self_scan.json")
    parser.add_argument("--api-txt", default="api/self_scan.txt")
    parser.add_argument("--seed", default=None)
    args = parser.parse_args()
    if not 0.3 <= args.timeout <= 15 or not 1 <= args.limit <= 100:
        parser.error("Bad timeout or limit")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{2,48}", args.label):
        parser.error("Bad probe label")
    hosts = validate_hosts(args.hosts.split(","))
    now = dt.datetime.now(dt.timezone.utc)
    with requests.Session() as session:
        networks = official_networks(session)
    checked, passed = rank_ips(networks, hosts, args.per_prefix,
                               args.seed or now.strftime("%Y-%m-%d"),
                               args.workers, args.timeout)
    if len(passed) < args.limit:
        raise SystemExit(f"Only {len(passed)} valid / {len(checked)} scanned. Previous files preserved.")
    payload = {
        "generated_at": now.isoformat(timespec="seconds"),
        "source": IP_RANGES_URL,
        "measurement_origin": args.label,
        "carrier_verified": False,
        "note": "Measured from this machine, not mainland China carrier probes.",
        "hosts": hosts, "scanned": len(checked),
        "passed": len(passed), "items": passed[:args.limit],
    }
    for name, body in [
        (args.output, json.dumps(payload, ensure_ascii=False, indent=2)+"\n"),
        (args.api_json, json.dumps(payload, ensure_ascii=False, indent=2)+"\n"),
        (args.api_txt, "\n".join(row["ip"] for row in passed[:args.limit])+"\n"),
    ]:
        file = Path(name)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(body, encoding="utf-8")
    print(f"Self-scan: {len(checked)} tested, {len(passed)} passed, {args.limit} published")
    print("Observation network:", args.label, "(not a China mainland 3-carrier ranking)")


if __name__ == "__main__":
    main()
