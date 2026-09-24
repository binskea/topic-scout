#!/usr/bin/env bash
# Fetch one live Wikimedia/Wikidata/MediaWiki URL through the deployed relay
# Worker and save it exactly like curiosity-radar/references/verify_live_api.sh
# does, so the output drops straight into tests/cassettes/ or feeds
# evals/generate_cassettes.py for a new topic/language scenario.
#
# Usage:
#   ./fetch_via_relay.sh <label> <output.json> "<https target url>"
#
# Requires:
#   RELAY_URL        e.g. https://curiosity-radar-wikimedia-relay.<subdomain>.workers.dev
#   RELAY_TOKEN       the X-Relay-Token secret (or pass --token-file <path>)
# Reads the token from ./.relay-token if RELAY_TOKEN isn't already set.

set -euo pipefail

if [ "$#" -lt 3 ]; then
  echo "Usage: $0 <label> <output.json> <https target url>" >&2
  exit 1
fi

label="$1"; file="$2"; target="$3"
: "${RELAY_URL:?Set RELAY_URL to the deployed worker's URL}"

if [ -z "${RELAY_TOKEN:-}" ]; then
  token_file="$(dirname "$0")/.relay-token"
  [ -f "$token_file" ] || { echo "No RELAY_TOKEN set and $token_file not found" >&2; exit 1; }
  RELAY_TOKEN="$(cat "$token_file")"
fi

out="$(dirname "$file")"
[ "$out" = "." ] || mkdir -p "$out"
headers="${file%.json}_headers.txt"

encoded_target="$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$target")"

curl -sS -D "$headers" \
  -H "X-Relay-Token: ${RELAY_TOKEN}" \
  "${RELAY_URL%/}/relay?url=${encoded_target}" \
  -o "$file"

code="$(head -1 "$headers" | tr -d '\r')"
echo "[$label] $code -> $file  (upstream: $target)"
