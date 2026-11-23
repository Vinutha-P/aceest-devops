#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Demonstrate all deployment strategies through the ingress and save the output
# as evidence in docs/evidence/strategies-<timestamp>.txt
#
#   BASE_URL=http://127.0.0.1 scripts/demo-strategies.sh      (minikube tunnel)
#   BASE_URL=https://xxxx.ngrok-free.app scripts/demo-strategies.sh
# -----------------------------------------------------------------------------
set -uo pipefail
BASE_URL="${BASE_URL:-http://127.0.0.1}"
REQUESTS="${REQUESTS:-20}"
OUT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/docs/evidence"
mkdir -p "$OUT_DIR"
OUT="${OUT_DIR}/strategies-$(date +%Y%m%d-%H%M%S).txt"
# python3 on macOS/Ubuntu, python on Windows (Git Bash)
PY=python3; "$PY" -c "" 2>/dev/null || PY=python

version_of() {  # prints "version track" for one request
  curl -s "$@" | "$PY" -c "import json,sys; d=json.load(sys.stdin); print(d['version'], d['track'])" \
    2>/dev/null || echo "ERROR"
}

distribution() {  # <path> [curl args...] -> counts of version/track over N requests
  local path="$1"; shift
  for _ in $(seq 1 "$REQUESTS"); do version_of "$@" "${BASE_URL}${path}"; done | sort | uniq -c
}

{
  echo "ACEest deployment strategy demo - $(date)"
  echo "Base URL: ${BASE_URL}   Requests per check: ${REQUESTS}"
  echo
  echo "== 1. Rolling update  (${BASE_URL}/rolling/version)"
  distribution /rolling/version
  echo
  echo "== 2. Blue-green  (${BASE_URL}/bluegreen/version) - all traffic on ONE colour"
  distribution /bluegreen/version
  echo
  echo "== 3. Canary  (${BASE_URL}/canary/version) - mostly stable, ~weight% canary"
  distribution /canary/version
  echo
  echo "== 4. A/B testing  (${BASE_URL}/ab/version)"
  echo "-- default users (variant A):"
  distribution /ab/version
  echo "-- users with header X-Variant: B:"
  distribution /ab/version -H "X-Variant: B"
  echo "-- users with cookie ab_variant=always:"
  distribution /ab/version --cookie "ab_variant=always"
  echo
  echo "== 5. Shadow  (${BASE_URL}/shadow/version) - users only see the primary"
  distribution /shadow/version
  echo "-- shadow pod access log (mirrored requests):"
  kubectl -n aceest logs deployment/aceest-shadow-new --tail=5 2>/dev/null \
    || echo "(kubectl not available here - run: kubectl -n aceest logs deploy/aceest-shadow-new)"
  echo
  echo "== Cluster state"
  kubectl -n aceest get deployments -o wide 2>/dev/null
  kubectl -n aceest get svc aceest-bluegreen -o jsonpath='{"bluegreen live colour: "}{.spec.selector.color}{"\n"}' 2>/dev/null
  kubectl -n aceest get ingress aceest-canary-new \
    -o jsonpath='{"canary weight: "}{.metadata.annotations.nginx\.ingress\.kubernetes\.io/canary-weight}{"%\n"}' 2>/dev/null
} | tee "$OUT"

echo
echo "Saved to ${OUT}"
