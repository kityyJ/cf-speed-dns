#!/usr/bin/env python3
"""Sync validated, carrier-balanced Cloudflare IPs into DNS A records.

The upstream pools supply the carrier rankings. Connectivity checks from a
GitHub runner are only an availability guard, not a China-network speed test.
"""

import ipaddress
import json
import os
import re
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from aggregate_ips import fetch_cf_networks

ROOT = Path(__file__).resolve().parent
API_ROOT = "https://api.cloudflare.com/client/v4"
REQUEST_TIMEOUT = 20


class DnsSyncError(RuntimeError):
    pass


def cf_api(session, method, endpoint, token, **kwargs):
    url = API_ROOT + endpoint
    try:
        response = session.request(
            method, url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=REQUEST_TIMEOUT, **kwargs,
        )
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise DnsSyncError(f"Cloudflare API request failed ({method} {endpoint}): {exc}") from exc
    if not isinstance(payload, dict):
        raise DnsSyncError(f"Unexpected Cloudflare API response ({method} {endpoint})")
    if response.status_code >= 400 or payload.get("success") is not True:
        errors = payload.get("errors", []) if isinstance(payload, dict) else []
        raise DnsSyncError(f"Cloudflare API rejected {method} {endpoint}: HTTP {response.status_code}; {errors}")
    return payload


def dns_records(session, zone_id, dns_name, token):
    """Query exact A records, across all pages (not the first zone page)."""
    found = []
    page = 1
    while True:
        payload = cf_api(
            session, "GET", f"/zones/{zone_id}/dns_records", token,
            params={"name.exact": dns_name, "type": "A", "page": page, "per_page": 100},
        )
        found.extend(
            rec for rec in payload.get("result", [])
            if rec.get("name") == dns_name and rec.get("type") == "A"
        )
        total_pages = int(payload.get("result_info", {}).get("total_pages", 1))
        if page >= total_pages:
            break
        page += 1
    return sorted(found, key=lambda rec: rec["id"])


def load_status(root=ROOT):
    path = root / "data" / "status.json"
    try:
        status = json.loads(path.read_text(encoding="utf-8"))
        updated = datetime.strptime(status["generated_at"], "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise DnsSyncError(f"IP pool status is missing or invalid: {exc}") from exc
    age = datetime.now(timezone.utc) - updated
    if not -timedelta(minutes=5) <= age <= timedelta(hours=2):
        raise DnsSyncError(f"IP pool is stale: generated at {updated.isoformat()}")
    if int(status.get("healthy_sources", 0)) <= 0:
        raise DnsSyncError("No working upstream IP sources; DNS records were not changed")
    return status


def load_pool(group, root=ROOT):
    path = root / "api" / f"{group}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload["items"]
        if not isinstance(items, list):
            raise ValueError("items is not an array")
        return items
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise DnsSyncError(f"IP pool {group} is missing or invalid: {exc}") from exc


def valid_cf_ip(item, networks):
    try:
        if int(item.get("port", 443)) != 443:
            return None
        address = ipaddress.ip_address(item["ip"])
        if address.version != 4 or not address.is_global:
            return None
        if not any(address in network for network in networks):
            return None
        return str(address)
    except (AttributeError, KeyError, TypeError, ValueError):
        return None



def reported_metrics(item):
    """Read upstream-reported RTT and throughput from descriptive IP tags."""
    tag = str(item.get("tag", ""))
    latency = re.search(r"(?<!\d)(\d+(?:\.\d+)?)\s*ms\b", tag, re.IGNORECASE)
    speed = re.search(r"(?<!\d)(\d+(?:\.\d+)?)\s*mb/s\b", tag, re.IGNORECASE)
    rtt_ms = float(latency.group(1)) if latency else None
    speed_mb = float(speed.group(1)) if speed else None
    return rtt_ms, speed_mb


def candidate_rank(item, index):
    """Prefer measured, usable low RTT; then geographically plausible CN routes.

    Missing RTT is not treated as zero RTT. Upstream measurements come from
    their own probes, not GitHub Actions runners or the end user's network.
    """
    rtt, speed = reported_metrics(item)
    if speed is not None and speed < 1.0:
        return None  # A low RTT with almost no throughput is not a good endpoint.
    if rtt is not None and 0 < rtt <= 180:
        return (0, rtt, index)
    label = (str(item.get("tag", "")) + " " + str(item.get("source", ""))).upper()
    if any(token in label for token in ("HKG", "HONG KONG", "香港")):
        region = 0
    elif any(token in label for token in ("TPE", "TWN", "TAIPEI", "台湾")):
        region = 1
    elif any(token in label for token in ("NRT", "TYO", "TOKYO", "日本", "东京")):
        region = 2
    elif any(token in label for token in ("SIN", "SINGAPORE", "新加坡")):
        region = 3
    elif any(token in label for token in ("LAX", "SJC", "SFO", "FRA", "LHR")):
        region = 6
    else:
        region = 4
    return (1, region, index)


def pick_ips(pools, count, networks, probe=None):
    """Select low-latency candidates, 1/3 per China carrier when possible."""
    carriers = ("ct", "cu", "cmcc")
    quota = {carrier: count // 3 + (i < count % 3)
             for i, carrier in enumerate(carriers)}
    ordered = {}
    for group in (*carriers, "all"):
        candidates = []
        for index, item in enumerate(pools[group]):
            rank = candidate_rank(item, index)
            if rank is not None:
                candidates.append((rank, item))
        ordered[group] = [item for _, item in sorted(candidates, key=lambda p: p[0])]

    selected = []
    seen = set()
    checked = {}
    chosen_by_carrier = dict.fromkeys(carriers, 0)
    cursors = dict.fromkeys(carriers, 0)

    def try_add(item, carrier=None):
        ip = valid_cf_ip(item, networks)
        if not ip or ip in seen:
            return False
        if ip not in checked:
            checked[ip] = bool(probe(ip)) if probe is not None else True
        if not checked[ip]:
            return False
        seen.add(ip)
        selected.append(ip)
        if carrier:
            chosen_by_carrier[carrier] += 1
        return True

    # Interleave low-RTT candidates across CT / CU / CMCC to avoid single-network bias.
    while len(selected) < count and any(chosen_by_carrier[g] < quota[g] for g in carriers):
        advanced = False
        for group in carriers:
            if chosen_by_carrier[group] >= quota[group]:
                continue
            while cursors[group] < len(ordered[group]):
                item = ordered[group][cursors[group]]
                cursors[group] += 1
                if try_add(item, group):
                    advanced = True
                    break
            if len(selected) >= count:
                break
        if not advanced:
            break

    # A carrier may have fewer usable IPs; borrow from other carrier pools and all.
    for group in (*carriers, "all"):
        for item in ordered[group]:
            if len(selected) >= count:
                break
            try_add(item)
        if len(selected) >= count:
            break

    if len(selected) < count:
        raise DnsSyncError(
            f"Only {len(selected)} validated IPs for a target of {count}; DNS unchanged"
        )
    print(f"Carrier priorities: {chosen_by_carrier}; unknown RTT stays unscored")
    return selected


def tcp_reachable(ip, timeout=2.0):
    try:
        with socket.create_connection((ip, 443), timeout=timeout):
            return True
    except OSError:
        return False



def sync_dns(session, zone_id, dns_name, token, records, desired):
    """Update, create or remove only exact-name DNS-only A records."""
    if not records:
        raise DnsSyncError(f"No existing A records for {dns_name}; refusing to create DNS blindly")
    if len(set(desired)) != len(desired):
        raise DnsSyncError("Duplicate candidate IPs; refusing to change DNS")
    if any(
        rec.get("proxied") is not False
        or rec.get("name", dns_name) != dns_name
        or rec.get("type", "A") != "A"
        for rec in records
    ):
        raise DnsSyncError("Unexpected record name/type or orange-cloud proxy; DNS untouched")

    matched_ids = set()
    matched_ips = set()
    for ip in desired:
        for rec in records:
            if rec["id"] not in matched_ids and rec.get("content") == ip:
                matched_ids.add(rec["id"])
                matched_ips.add(ip)
                break

    unused = [rec for rec in records if rec["id"] not in matched_ids]
    missing_ips = [ip for ip in desired if ip not in matched_ips]
    changed = []

    # PATCH and POST before DELETE so partial failures cannot shrink the DNS pool.
    for rec, ip in zip(unused, missing_ips):
        cf_api(session, "PATCH", f"/zones/{zone_id}/dns_records/{rec['id']}", token,
               json={"content": ip})
        changed.append((rec.get("content"), ip))
        print(f"Updated {dns_name}: {rec.get('content')} -> {ip}")
    for ip in missing_ips[len(unused):]:
        cf_api(session, "POST", f"/zones/{zone_id}/dns_records", token,
               json={"type": "A", "name": dns_name, "content": ip, "ttl": 1,
                     "proxied": False, "comment": "[CF-IP] cook-speed 优选地址自动维护"})
        changed.append((None, ip))
        print(f"Created {dns_name}: {ip}")

    removable = unused[len(missing_ips):]
    for rec in removable:
        cf_api(session, "DELETE", f"/zones/{zone_id}/dns_records/{rec['id']}", token)
        changed.append((rec.get("content"), None))
        print(f"Removed extra A record: {dns_name} -> {rec.get('content')}")
    if not changed:
        print(f"{dns_name}: {len(desired)} IPs are already current; no DNS changes")
    return changed


def pushplus(message):
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token:
        return
    try:
        response = requests.post(
            "https://www.pushplus.plus/send",
            json={"token": token, "title": "Cloudflare 优选 DNS", "content": message,
                  "template": "markdown", "channel": "wechat"},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Optional PushPlus notification failed: {exc}")


def main():
    token = os.environ.get("CF_API_TOKEN")
    zone_id = os.environ.get("CF_ZONE_ID")
    dns_name = os.environ.get("CF_DNS_NAME", "").strip().lower().rstrip(".")
    if not all((token, zone_id, dns_name)):
        raise DnsSyncError("Required secrets: CF_API_TOKEN, CF_ZONE_ID, CF_DNS_NAME")
    if "." not in dns_name or "*" in dns_name:
        raise DnsSyncError("CF_DNS_NAME must be a fully qualified DNS hostname")

    session = requests.Session()
    records = dns_records(session, zone_id, dns_name, token)
    if not records:
        raise DnsSyncError(f"No A records found for {dns_name}")
    target = os.environ.get("CF_DNS_RECORD_COUNT", "").strip()
    try:
        count = int(target) if target else len(records)
    except ValueError as exc:
        raise DnsSyncError("CF_DNS_RECORD_COUNT must be an integer") from exc
    if not 1 <= count <= 30:
        raise DnsSyncError("CF_DNS_RECORD_COUNT must be between 1 and 30")
    print(f"Checking {len(records)} existing A records for {dns_name}, target={count}")

    load_status()
    networks, source = fetch_cf_networks(session, 10)
    print(f"Cloudflare CIDR source: {source}")
    pools = {group: load_pool(group) for group in ("ct", "cu", "cmcc", "all")}
    check_enabled = os.environ.get("CF_DNS_TCP_CHECK", "1") not in ("0", "false", "no")
    probe = tcp_reachable if check_enabled else None
    desired = pick_ips(pools, count, networks, probe=probe)
    print(f"Selected IPs (CT/CU/CMCC first): {', '.join(desired)}")
    updates = sync_dns(session, zone_id, dns_name, token, records, desired)
    pushplus(f"{dns_name}: {len(updates)} DNS changes, {count - len(updates)} unchanged. IPs: {', '.join(desired)}")


if __name__ == "__main__":
    try:
        main()
    except DnsSyncError as exc:
        print(f"DNS sync failed: {exc}", file=sys.stderr)
        sys.exit(1)
