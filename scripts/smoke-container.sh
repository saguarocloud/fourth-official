#!/usr/bin/env bash
# Run an image and verify it serves a healthy /healthz with the expected identity, as a non-root user.
# Usage: scripts/smoke-container.sh <image> <container-port> <expected-service> <expected-version>
set -euo pipefail

USAGE="usage: $0 <image> <container-port> <expected-service> <expected-version>"
IMAGE="${1:?$USAGE}" PORT="${2:?$USAGE}" SERVICE="${3:?$USAGE}" VERSION="${4:?$USAGE}"
for tool in docker curl jq; do
  command -v "$tool" >/dev/null || { echo "FAIL: $tool is required"; exit 2; }
done

NAME="smoke-${SERVICE}-$$"
TIMEOUT_SECONDS=60

fail() {
  echo "FAIL: $*"
  echo "--- container logs ---"
  docker logs "$NAME" 2>&1 | tail -50 || true
  exit 1
}
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$NAME" -p "127.0.0.1::${PORT}" "$IMAGE" >/dev/null
HOST_PORT="$(docker port "$NAME" "$PORT/tcp" 2>/dev/null | head -1 | awk -F: '{print $NF}')" \
  || fail "port $PORT is not published"
[[ -n "$HOST_PORT" ]] || fail "port $PORT is not published"
URL="http://127.0.0.1:${HOST_PORT}/healthz"

deadline=$((SECONDS + TIMEOUT_SECONDS))
until body="$(curl -fsS --max-time 5 "$URL" 2>/dev/null)"; do
  [[ "$(docker inspect -f '{{.State.Running}}' "$NAME")" == "true" ]] || fail "container exited before becoming healthy"
  (( SECONDS < deadline )) || fail "$URL not healthy after ${TIMEOUT_SECONDS}s"
  sleep 1
done

expected="$(jq -cnS --arg s "$SERVICE" --arg v "$VERSION" '{status: "ok", service: $s, version: $v}')"
actual="$(jq -cS . <<<"$body")"
[[ "$actual" == "$expected" ]] || fail "unexpected health payload: $actual (expected $expected)"

uid="$(docker exec "$NAME" id -u)"
[[ "$uid" != "0" ]] || fail "container runs as root"

echo "PASS: $SERVICE $VERSION healthy at $URL (uid $uid)"
