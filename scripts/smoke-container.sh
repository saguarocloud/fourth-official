#!/usr/bin/env bash
# Run an image and verify it serves a healthy /healthz with the expected identity, as a non-root user.
# Usage: scripts/smoke-container.sh <image> <container-port> <expected-service> <expected-version>
set -euo pipefail

IMAGE="$1" PORT="$2" SERVICE="$3" VERSION="$4"
NAME="smoke-${SERVICE}-$$"
TIMEOUT_SECONDS=60

cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$NAME" -p "127.0.0.1::${PORT}" "$IMAGE" >/dev/null
HOST_PORT="$(docker port "$NAME" "$PORT/tcp" | head -1 | awk -F: '{print $NF}')"
URL="http://127.0.0.1:${HOST_PORT}/healthz"

deadline=$((SECONDS + TIMEOUT_SECONDS))
until body="$(curl -fsS "$URL" 2>/dev/null)"; do
  if (( SECONDS >= deadline )); then
    echo "FAIL: $URL not healthy after ${TIMEOUT_SECONDS}s"; docker logs "$NAME"; exit 1
  fi
  sleep 1
done

expected="$(jq -cn --arg s "$SERVICE" --arg v "$VERSION" '{status: "ok", service: $s, version: $v}')"
actual="$(jq -cS . <<<"$body")"
if [[ "$actual" != "$(jq -cS . <<<"$expected")" ]]; then
  echo "FAIL: unexpected health payload: $actual (expected $expected)"; exit 1
fi

uid="$(docker exec "$NAME" id -u)"
if [[ "$uid" == "0" ]]; then
  echo "FAIL: container runs as root"; exit 1
fi

echo "PASS: $SERVICE $VERSION healthy at $URL (uid $uid)"
