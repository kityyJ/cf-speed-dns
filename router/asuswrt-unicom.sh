#!/bin/sh
# ASUSWRT ARMv7 / BusyBox: independent Cloudflare IPv4 scan over local WAN.
# No third-party IP lists, no API tokens, no DNS changes, no open ports.
set -e
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
LC_ALL=C
export LC_ALL

if [ -z "$HOST_A" ]; then
  echo "Set HOST_A to an HTTPS hostname (example: HOST_A=www.example.com)." >&2
  exit 2
fi
if [ -z "$PER_PREFIX" ]; then PER_PREFIX=8; fi
if [ -z "$LIMIT" ]; then LIMIT=30; fi
if [ -z "$MIN_PASS" ]; then MIN_PASS=1; fi
if [ -z "$CONNECT_TIMEOUT" ]; then CONNECT_TIMEOUT=3; fi
if [ -z "$MAX_TIME" ]; then MAX_TIME=7; fi
if [ -z "$OUT_DIR" ]; then OUT_DIR=/jffs/cf-selfscan; fi

case "$HOST_A" in *[!a-zA-Z0-9.-]* | '' | *..* ) echo "Bad HOST_A" >&2; exit 2;; esac
case "$HOST_B" in *[!a-zA-Z0-9.-]* | *..* ) echo "Bad HOST_B" >&2; exit 2;; esac
for value in "$PER_PREFIX" "$LIMIT" "$MIN_PASS" "$CONNECT_TIMEOUT" "$MAX_TIME"; do
  case "$value" in *[!0-9]* | '') echo "Numeric setting expected" >&2; exit 2;; esac
done
[ "$PER_PREFIX" -ge 1 ] && [ "$PER_PREFIX" -le 32 ] || exit 2
[ "$LIMIT" -ge 1 ] && [ "$LIMIT" -le 100 ] || exit 2
[ "$MIN_PASS" -ge 1 ] && [ "$MIN_PASS" -le "$LIMIT" ] || exit 2
[ "$CONNECT_TIMEOUT" -ge 1 ] && [ "$MAX_TIME" -ge "$CONNECT_TIMEOUT" ] || exit 2

for program in curl awk sort head wc date mkdir rm mv chmod; do
  if ! type "$program" >/dev/null 2>&1; then
    echo "Required command missing: $program" >&2
    exit 2
  fi
done

LOCK=/tmp/cf-selfscan.lock
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "Scan already running; refuse parallel scan" >&2
  exit 1
fi
WORK=/tmp/cf-selfscan.$$
mkdir "$WORK"
trap 'rm -rf "$WORK" "$LOCK"' 0
trap 'exit 2' 1 2 3 15

# The one and only source of IP candidate ranges: Cloudflare itself.
if ! curl -q --noproxy '*' -4 -fLsS --connect-timeout 5 --max-time 20 \
  https://www.cloudflare.com/ips-v4 -o "$WORK/official-cidrs"; then
  echo "Official Cloudflare list unavailable; previous results preserved" >&2
  exit 1
fi
cidr_count=$(wc -l < "$WORK/official-cidrs")
if [ "$cidr_count" -lt 10 ] || [ "$cidr_count" -gt 100 ]; then
  echo "Unexpected CIDR count; not scanning" >&2
  exit 1
fi

# AWK uses numeric IPv4 math: choose random hosts within each official CIDR.
awk -v per="$PER_PREFIX" -v seed="$(date +%s)" '
function dotted(n, a,b,c,d) {
  a=int(n/16777216); n-=a*16777216
  b=int(n/65536); n-=b*65536
  c=int(n/256); d=int(n-c*256)
  return a "." b "." c "." d
}
BEGIN { srand(seed); valid=0; bad=0 }
{
  split($0, pair, "/")
  n=split(pair[1], octets, ".")
  mask=pair[2]+0
  if (n!=4 || mask<8 || mask>30 || pair[2] !~ /^[0-9]+$/) { bad++; next }
  base=octets[1]*16777216+octets[2]*65536+octets[3]*256+octets[4]
  size=2^(32-mask)
  base=int(base/size)*size
  for (i=0; i<per; i++) {
    offset=1+int(rand()*(size-2))
    print dotted(base+offset)
  }
  valid++
}
END { if (bad>0 || valid<10) exit 1 }
' "$WORK/official-cidrs" | sort -u > "$WORK/candidates"
count=$(wc -l < "$WORK/candidates")
if [ "$count" -lt 10 ]; then
  echo "Candidate generation failed" >&2
  exit 1
fi

# curl --resolve preserves hostname SNI and cert verification while forcing IP.
# No -k / --insecure: invalid certificate = failed measurement.
probe() {
  ip="$1"
  host="$2"
  raw=$(curl -q --noproxy '*' -4 -sS -o /dev/null \
    --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" \
    --resolve "$host:443:$ip" \
    -w '%{http_code}|%{time_connect}|%{time_appconnect}|%{time_starttransfer}|%{time_total}|%{remote_ip}' \
    "https://$host/" 2>/dev/null) || return 1
  converted=$(printf '%s\n' "$raw" | awk -F '|' -v expected="$ip" '
  $1 ~ /^2[0-9][0-9]$/ && $6==expected && $2>0 && $3>0 && $4>0 && $5>0 {
    printf "%.2f|%.2f|%.2f|%.2f", 1000*$2, 1000*($3-$2), 1000*$4, 1000*$5
  }')
  [ -n "$converted" ] || return 1
  printf '%s\n' "$converted"
}

: > "$WORK/measured"
examined=0
while IFS= read -r ip; do
  examined=$((examined+1))
  first=$(probe "$ip" "$HOST_A") || continue
  if [ -n "$HOST_B" ]; then
    second=$(probe "$ip" "$HOST_B") || continue
  else
    second="$first"
  fi
  metrics=$(printf '%s\n%s\n' "$first" "$second" | awk -F '|' '
    {tcp+=$1; tls+=$2; ttfb+=$3; total+=$4; n++}
    END {if(n==2) printf "%.2f %.2f %.2f %.2f", tcp/2, tls/2, ttfb/2, total/2}')
  [ -n "$metrics" ] && printf '%s %s\n' "$ip" "$metrics" >> "$WORK/measured"
  if [ $((examined%30)) -eq 0 ]; then echo "Checked $examined/$count"; fi
done < "$WORK/candidates"

passed=$(wc -l < "$WORK/measured")
if [ "$passed" -lt "$MIN_PASS" ]; then
  echo "Only $passed IPs passed; previous results preserved" >&2
  exit 1
fi
sort -n -k4,4 "$WORK/measured" | head -n "$LIMIT" > "$WORK/best"
selected=$(wc -l < "$WORK/best")

mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"
tmpjson="$OUT_DIR/.self-scan.$$.json"
tmptxt="$OUT_DIR/.self-scan.$$.txt"
trap 'rm -f "$tmpjson" "$tmptxt"; rm -rf "$WORK" "$LOCK"' 0

awk '{print $1}' "$WORK/best" > "$tmptxt"
{
  printf '{\n'
  printf '  "generated_at": "%s",\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '  "source": "https://www.cloudflare.com/ips-v4",\n'
  printf '  "measurement_origin": "user-operated-unicom-home-router",\n'
  printf '  "carrier": "cu",\n'
  printf '  "carrier_verified": false,\n'
  printf '  "note": "Measured locally on router; China Unicom network is user-declared. Not a nationwide benchmark.",\n'
  printf '  "target_hosts": ["%s"' "$HOST_A"
  if [ -n "$HOST_B" ]; then printf ', "%s"' "$HOST_B"; fi
  printf '],\n'
  printf '  "tested": %s,\n  "passed": %s,\n  "count": %s,\n' "$count" "$passed" "$selected"
  printf '  "items": [\n'
  idx=0
  while read -r ip tcp tls ttfb total; do
    if [ "$idx" -gt 0 ]; then printf ',\n'; fi
    printf '    {"ip":"%s","port":443,"tcp_ms":%s,"tls_ms":%s,"ttfb_ms":%s,"total_ms":%s}' \
      "$ip" "$tcp" "$tls" "$ttfb" "$total"
    idx=$((idx+1))
  done < "$WORK/best"
  printf '\n  ]\n}\n'
} > "$tmpjson"

mv "$tmpjson" "$OUT_DIR/self_scan_cu.json"
mv "$tmptxt" "$OUT_DIR/self_scan_cu.txt"
echo "Done: $count checked, $passed passed, $selected saved"
echo "JSON: $OUT_DIR/self_scan_cu.json"
echo "TXT:  $OUT_DIR/self_scan_cu.txt"
