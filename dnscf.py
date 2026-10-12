#!/usr/bin/env python3
"""Sync validated, carrier-diverse Cloudflare IPs into existing DNS A records.

The upstream pools supply the carrier rankings. Connectivity checks from a
GitHub runner are only an availability guard, not a China-network speed test.
"""

import ipaddress
import json
import os
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


def pick_ips(pools, count, networks, probe=None):
    """Prefer one IP per carrier; fill from all sources, dedupe and verify."""
    selected = []
    seen = set()
    checked = {}

    def add_first(group):
        for item in pools[group]:
            ip = valid_cf_ip(item, networks)
            if not ip or ip in seen:
                continue
            if ip not in checked:
                checked[ip] = True if probe is None else probe(ip)
            if not checked[ip]:
                continue
            seen.add(ip)
            selected.append(ip)
            return True
        return False

    for group in ("ct", "cu", "cmcc"):
        if len(selected) >= count:
            break
        add_first(group)
    if len(selected) < count:
        for group in ("all", "ct", "cu", "cmcc"):
            for item in pools[group]:
                if len(selected) >= count:
                    break
                ip = valid_cf_ip(item, networks)
                if not ip or ip in seen:
                    continue
                if ip not in checked:
                    checked[ip] = True if probe is None else probe(ip)
                if checked[ip]:
                    seen.add(ip)
                    selected.append(ip)
            if len(selected) >= count:
                break
    if len(selected) < count:
        raise DnsSyncError(f"Only {len(selected)} valid and reachable IPs for {count} DNS records; no changes made")
    return selected


def tcp_reachable(ip, timeout=2.0):
    try:
        with socket.create_connection((ip, 443), timeout=timeout):
            return True
    except OSError:
        return False


def sync_dns(session, zone_id, dns_name, token, records, desired):
    """Keep matching records unchanged; PATCH only addresses needing replacement."""
    if not records:
        raise DnsSyncError(f"No existing A records for {dns_name}; refusing to create an unexpected DNS name")
    if len(records) != len(desired):
        raise DnsSyncError("Candidate IP count does not match DNS A record count")
    if any(rec.get("proxied") is True for rec in records):
        raise DnsSyncError("Some A records are proxied; disable the orange cloud before using CF edge IPs")

    matched_ids = set()
    matched_ips = set()
    for ip in desired:
        for rec in records:
            if rec["id"] not in matched_ids and rec.get("content") == ip:
                matched_ids.add(rec["id"])
                matched_ips.add(ip)
                break
    remaining_records = [rec for rec in records if rec["id"] not in matched_ids]
    remaining_ips = [ip for ip in desired if ip not in matched_ips]
    updates = []
    for rec, ip in zip(remaining_records, remaining_ips):
        cf_api(
            session, "PATCH", f"/zones/{zone_id}/dns_records/{rec['id']}", token,
            json={"content": ip},
        )
        updates.append((rec.get("content"), ip))
        print(f"Updated {dns_name}: {rec.get('content')} -> {ip}")
    if not updates:
        print(f"{dns_name}: {len(desired)} IPs are already current; no DNS changes")
    return updates


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
    print(f"Checking {len(records)} existing A records for {dns_name}")

    load_status()
    networks, source = fetch_cf_networks(session, 10)
    print(f"Cloudflare CIDR source: {source}")
    pools = {group: load_pool(group) for group in ("ct", "cu", "cmcc", "all")}
    check_enabled = os.environ.get("CF_DNS_TCP_CHECK", "1") not in ("0", "false", "no")
    probe = tcp_reachable if check_enabled else None
    desired = pick_ips(pools, len(records), networks, probe=probe)
    print(f"Selected IPs (CT/CU/CMCC first): {', '.join(desired)}")
    updates = sync_dns(session, zone_id, dns_name, token, records, desired)
    pushplus(f"{dns_name}: {len(updates)} updated, {len(records) - len(updates)} unchanged. IPs: {', '.join(desired)}")


if __name__ == "__main__":
    try:
        main()
    except DnsSyncError as exc:
        print(f"DNS sync failed: {exc}", file=sys.stderr)
        sys.exit(1)
