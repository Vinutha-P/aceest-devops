#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Manually revert a strategy to its last stable version.
#   scripts/rollback.sh <rolling|blue-green|canary|ab|shadow> [revision]
# (deploy.sh already rolls back automatically when a deployment fails.)
# -----------------------------------------------------------------------------
set -euo pipefail

STRATEGY="${1:?usage: rollback.sh <rolling|blue-green|canary|ab|shadow> [revision]}"
REVISION="${2:-}"
NS="${NAMESPACE:-aceest}"
TIMEOUT="${ROLLOUT_TIMEOUT:-180s}"
kc() { kubectl -n "$NS" "$@"; }
log() { echo "[rollback] $*"; }

undo() {
  local deployment="$1"
  kc rollout history "deployment/${deployment}"
  if [ -n "$REVISION" ]; then
    kc rollout undo "deployment/${deployment}" --to-revision="$REVISION"
  else
    kc rollout undo "deployment/${deployment}"
  fi
  kc rollout status "deployment/${deployment}" --timeout="$TIMEOUT"
  log "${deployment} now runs: $(kc get deployment "$deployment" \
        -o jsonpath='{.spec.template.spec.containers[0].image}')"
}

case "$STRATEGY" in
  rolling) undo aceest-rolling ;;
  blue-green)
    active="$(kc get service aceest-bluegreen -o jsonpath='{.spec.selector.color}')"
    if [ "$active" = "blue" ]; then previous="green"; else previous="blue"; fi
    log "Switching live traffic back ${active} -> ${previous}"
    kc patch service aceest-bluegreen -p "{\"spec\":{\"selector\":{\"color\":\"${previous}\"}}}"
    kc patch service aceest-bluegreen-preview -p "{\"spec\":{\"selector\":{\"color\":\"${active}\"}}}"
    ;;
  canary)
    log "Stopping canary traffic (weight 0) and reverting the canary deployment"
    kc annotate ingress aceest-canary-new --overwrite nginx.ingress.kubernetes.io/canary-weight=0
    undo aceest-canary-new
    ;;
  ab) undo aceest-ab-b ;;
  shadow) undo aceest-shadow-new ;;
  *) echo "unknown strategy '${STRATEGY}'" >&2; exit 1 ;;
esac
log "Done."
