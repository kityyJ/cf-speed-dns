#!/bin/sh
set -eu
repo_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
tempdir=$(mktemp -d)
trap 'rm -rf "$tempdir"' 0
mkdir -p "$tempdir/bin"
cat > "$tempdir/bin/curl" <<'MOCK'
#!/bin/sh
out=""
resolved=""
last=""
for arg in "$@"; do
  if [ "$last" = "-o" ]; then out="$arg"; fi
  if [ "$last" = "--resolve" ]; then resolved="$arg"; fi
  last="$arg"
done
if [ -z "$resolved" ]; then
  cat > "$out" <<'CIDRS'
104.16.0.0/24
104.17.0.0/24
104.18.0.0/24
104.19.0.0/24
104.20.0.0/24
104.21.0.0/24
104.22.0.0/24
104.23.0.0/24
104.24.0.0/24
104.25.0.0/24
CIDRS
else
  ip=$(printf '%s\n' "$resolved" | awk -F : '{print $3}')
  printf '200|0.101|0.202|0.303|0.404|%s' "$ip"
fi
MOCK
chmod +x "$tempdir/bin/curl"

sed "s|^PATH=/usr/sbin:/usr/bin:/sbin:/bin$|PATH=$tempdir/bin:/usr/sbin:/usr/bin:/sbin:/bin|" \
  "$repo_root/router/asuswrt-unicom.sh" > "$tempdir/scan.sh"
sh -n "$tempdir/scan.sh"
HOST_A=alpha.example.com HOST_B=beta.example.com PER_PREFIX=2 \
 LIMIT=5 MIN_PASS=2 OUT_DIR="$tempdir/output" sh "$tempdir/scan.sh"

python3 - "$tempdir/output/self_scan_cu.json" "$tempdir/output/self_scan_cu.txt" <<'PY'
import ipaddress
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text())
ips = Path(sys.argv[2]).read_text().strip().splitlines()
assert len(ips) == 5
assert data["count"] == len(ips)
assert data["passed"] == 20 and data["tested"] == 20
assert data["carrier"] == "cu" and data["carrier_verified"] is False
assert [item["ip"] for item in data["items"]] == ips
assert all(item["ttfb_ms"] == 303 for item in data["items"])
assert all(item["tls_ms"] == 101 for item in data["items"])
assert all(ipaddress.ip_address(ip) in ipaddress.ip_network("104.16.0.0/12") for ip in ips)
print("Router shell scanner smoke test passed")
PY
