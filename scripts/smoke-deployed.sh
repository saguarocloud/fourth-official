#!/usr/bin/env bash
# Verify a deployed service answers /healthz with the expected identity and release version.
# Allows for a cold start: apps scale to zero, so the first request may wait for a replica.
# Usage: scripts/smoke-deployed.sh <base-url> <expected-service> <expected-version>
set -euo pipefail

USAGE="usage: $0 <base-url> <expected-service> <expected-version>"
BASE_URL="${1:?$USAGE}" SERVICE="${2:?$USAGE}" VERSION="${3:?$USAGE}"
for tool in curl jq; do
  command -v "$tool" >/dev/null || { echo "FAIL: $tool is required"; exit 2; }
done
[[ "$BASE_URL" == https://* ]] || { echo "FAIL: base URL must be https: '$BASE_URL'"; exit 2; }

URL="${BASE_URL%/}/healthz"
TIMEOUT_SECONDS="${SMOKE_TIMEOUT_SECONDS:-300}"

deadline=$((SECONDS + TIMEOUT_SECONDS))
last=""
while (( SECONDS < deadline )); do
  if body="$(curl -fsS --max-time 30 "$URL" 2>/dev/null)"; then
    last="$body"
    if [[ "$(jq -r '"\(.status) \(.service) \(.version)"' <<<"$body" 2>/dev/null)" == "ok $SERVICE $VERSION" ]]; then
      echo "PASS: $SERVICE $VERSION live at $URL"
      exit 0
    fi
  fi
  # A previous revision may still be serving while the new one activates.
  sleep 5
done

echo "FAIL: $URL did not report $SERVICE $VERSION within ${TIMEOUT_SECONDS}s (last response: ${last:-none})"
exit 1
