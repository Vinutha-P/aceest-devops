#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Deploy an ACEest image to Kubernetes with the chosen strategy.
# Used by the Jenkins "Deploy" stage; can also be run by hand (Git Bash / Linux).
#
#   scripts/deploy.sh <strategy> <image>
#   strategy: rolling | blue-green | canary | canary-promote | ab | shadow
#   example : scripts/deploy.sh canary myuser/aceest-fitness:3.2.4-b17
#
# Every strategy waits for the rollout, smoke-tests the new pods (GET /version
# must return the expected version) and ROLLS BACK AUTOMATICALLY on failure.
#
# Env: NAMESPACE (aceest), ROLLOUT_TIMEOUT (180s), CANARY_WEIGHT (20),
#      DOCKERHUB_USER (replaces the placeholder in k8s/*.yaml on first apply)
# -----------------------------------------------------------------------------
set -euo pipefail

STRATEGY="${1:-rolling}"
IMAGE="${2:?usage: deploy.sh <strategy> <image>}"
NS="${NAMESPACE:-aceest}"
TIMEOUT="${ROLLOUT_TIMEOUT:-180s}"
CANARY_WEIGHT="${CANARY_WEIGHT:-20}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="${SCRIPT_DIR}/../k8s"

# "user/aceest-fitness:3.2.4-b17" -> "3.2.4"
TAG="${IMAGE##*:}"
EXPECTED_VERSION="${TAG%%-b*}"

log()  { echo "[deploy] $*"; }
fail() { echo "[deploy] ERROR: $*" >&2; exit 1; }
kc()   { kubectl -n "$NS" "$@"; }

# Apply a strategy's manifests the first time only (later runs just change the image,
# so re-applying never resets a running deployment back to the manifest's tag).
ensure_strategy() {
  local folder="$1" deployment="$2"
  kubectl apply -f "${K8S_DIR}/namespace.yaml" >/dev/null
  bash "${SCRIPT_DIR}/ensure-secret.sh"
  if ! kc get deployment "$deployment" >/dev/null 2>&1; then
    log "First deployment of '${folder}' - applying manifests"
    for f in "${K8S_DIR}/${folder}"/*.yaml; do
      if [ -n "${DOCKERHUB_USER:-}" ]; then
        sed "s#your-dockerhub-username#${DOCKERHUB_USER}#g" "$f"
      else
        cat "$f"
      fi
    done | kubectl apply -f -
    kc rollout status "deployment/${deployment}" --timeout="$TIMEOUT" || true
  fi
}

set_image() {
  local deployment="$1"
  log "Updating ${deployment} -> ${IMAGE}"
  kc set image "deployment/${deployment}" app="$IMAGE"
  kc annotate "deployment/${deployment}" --overwrite \
    kubernetes.io/change-cause="Jenkins build ${BUILD_NUMBER:-manual}: ${IMAGE}"
}

wait_rollout() {
  kc rollout status "deployment/$1" --timeout="$TIMEOUT"
}

# smoke <service> <prefix> <deployment-to-exec-from>
# Calls http://<service>/<prefix>/version from inside the cluster and checks the version.
smoke() {
  local svc="$1" prefix="$2" from="$3" i
  local code="import json,sys,urllib.request
d=json.load(urllib.request.urlopen('http://${svc}/${prefix}/version',timeout=5))
print(d)
sys.exit(0 if d['version']=='${EXPECTED_VERSION}' else 1)"
  for i in 1 2 3 4 5 6; do
    if kc exec "deployment/${from}" -- python -c "$code"; then
      log "Smoke test passed: ${svc} serves v${EXPECTED_VERSION}"
      return 0
    fi
    log "Smoke test attempt ${i} failed, retrying..."
    sleep 5
  done
  return 1
}

undo() {
  log "ROLLING BACK deployment/$1 to the previous revision"
  kc rollout undo "deployment/$1"
  kc rollout status "deployment/$1" --timeout="$TIMEOUT" || true
}

# ---------------------------------------------------------------- strategies --

deploy_rolling() {
  ensure_strategy rolling aceest-rolling
  set_image aceest-rolling
  if wait_rollout aceest-rolling && smoke aceest-rolling rolling aceest-rolling; then
    kc rollout history deployment/aceest-rolling | tail -5
  else
    undo aceest-rolling
    fail "rolling update failed - previous version restored"
  fi
}

deploy_blue_green() {
  ensure_strategy blue-green aceest-blue
  local active idle
  active="$(kc get service aceest-bluegreen -o jsonpath='{.spec.selector.color}')"
  if [ "$active" = "blue" ]; then idle="green"; else idle="blue"; fi
  log "Live colour: ${active} | deploying to idle colour: ${idle}"

  set_image "aceest-${idle}"
  if ! wait_rollout "aceest-${idle}"; then
    undo "aceest-${idle}"
    fail "idle (${idle}) rollout failed - live traffic was never touched (${active})"
  fi

  kc patch service aceest-bluegreen-preview -p "{\"spec\":{\"selector\":{\"color\":\"${idle}\"}}}"
  if ! smoke aceest-bluegreen-preview bluegreen "aceest-${idle}"; then
    fail "preview smoke test failed - live traffic stays on ${active}"
  fi

  log "Switching live traffic ${active} -> ${idle}"
  kc patch service aceest-bluegreen -p "{\"spec\":{\"selector\":{\"color\":\"${idle}\"}}}"
  kc patch service aceest-bluegreen-preview -p "{\"spec\":{\"selector\":{\"color\":\"${active}\"}}}"

  if ! smoke aceest-bluegreen bluegreen "aceest-${idle}"; then
    log "Live check failed - switching back to ${active}"
    kc patch service aceest-bluegreen -p "{\"spec\":{\"selector\":{\"color\":\"${active}\"}}}"
    fail "blue-green switch rolled back to ${active}"
  fi
  log "Blue-green complete: ${idle} is live, ${active} kept as instant rollback target"
}

deploy_canary() {
  ensure_strategy canary aceest-canary-stable
  set_image aceest-canary-new
  if wait_rollout aceest-canary-new && smoke aceest-canary-new canary aceest-canary-new; then
    kc annotate ingress aceest-canary-new --overwrite \
      nginx.ingress.kubernetes.io/canary-weight="${CANARY_WEIGHT}"
    log "Canary live: ${CANARY_WEIGHT}% of /canary traffic -> v${EXPECTED_VERSION}"
  else
    kc annotate ingress aceest-canary-new --overwrite nginx.ingress.kubernetes.io/canary-weight=0
    undo aceest-canary-new
    fail "canary failed - weight set to 0 and canary rolled back"
  fi
}

deploy_canary_promote() {
  # Promote the canary image to the stable deployment, then stop splitting traffic
  local canary_image
  canary_image="$(kc get deployment aceest-canary-new -o jsonpath='{.spec.template.spec.containers[0].image}')"
  IMAGE="$canary_image"; TAG="${IMAGE##*:}"; EXPECTED_VERSION="${TAG%%-b*}"
  set_image aceest-canary-stable
  if wait_rollout aceest-canary-stable && smoke aceest-canary-stable canary aceest-canary-stable; then
    kc annotate ingress aceest-canary-new --overwrite nginx.ingress.kubernetes.io/canary-weight=0
    log "Canary promoted: stable now runs ${IMAGE}"
  else
    undo aceest-canary-stable
    fail "promotion failed - stable rolled back"
  fi
}

deploy_ab() {
  ensure_strategy ab-testing aceest-ab-a
  set_image aceest-ab-b
  if wait_rollout aceest-ab-b && smoke aceest-ab-b ab aceest-ab-b; then
    log "Variant B now runs v${EXPECTED_VERSION} (send header 'X-Variant: B' to /ab)"
  else
    undo aceest-ab-b
    fail "variant B rollout failed - rolled back"
  fi
}

deploy_shadow() {
  ensure_strategy shadow aceest-shadow-primary
  set_image aceest-shadow-new
  if wait_rollout aceest-shadow-new && smoke aceest-shadow-new shadow aceest-shadow-new; then
    log "Shadow now runs v${EXPECTED_VERSION}; it receives a mirror of /shadow traffic"
  else
    undo aceest-shadow-new
    fail "shadow rollout failed - rolled back"
  fi
}

log "Strategy=${STRATEGY} image=${IMAGE} expected version=${EXPECTED_VERSION} namespace=${NS}"
case "$STRATEGY" in
  rolling)        deploy_rolling ;;
  blue-green)     deploy_blue_green ;;
  canary)         deploy_canary ;;
  canary-promote) deploy_canary_promote ;;
  ab)             deploy_ab ;;
  shadow)         deploy_shadow ;;
  *) fail "unknown strategy '${STRATEGY}' (rolling|blue-green|canary|canary-promote|ab|shadow)" ;;
esac
log "Done."
