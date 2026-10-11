#!/usr/bin/env bash
# Lint the Bicep and fail on any warning or error (info-level findings are reported only).
# Used by CI and `make check-infra`, so both apply the same rules.
set -euo pipefail

command -v jq >/dev/null || { echo "FAIL: jq is required"; exit 2; }
sarif="$(mktemp)"
trap 'rm -f "$sarif"' EXIT

az bicep lint --file infra/main.bicep --diagnostics-format sarif > "$sarif"
findings="$(jq '[.runs[].results[] | select(.level == "warning" or .level == "error")]' "$sarif")"
if [[ "$(jq length <<<"$findings")" != "0" ]]; then
  jq -r '.[] | "\(.level): \(.message.text) (\(.locations[0].physicalLocation.artifactLocation.uri):\(.locations[0].physicalLocation.region.startLine))"' <<<"$findings"
  exit 1
fi
echo "PASS: Bicep lint clean"
