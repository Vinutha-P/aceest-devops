#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Create every deployment strategy in the cluster from k8s/ (first-time setup).
#   DOCKERHUB_USER=myuser scripts/bootstrap-k8s.sh
# -----------------------------------------------------------------------------
set -euo pipefail
: "${DOCKERHUB_USER:?set DOCKERHUB_USER to your Docker Hub username}"
K8S_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../k8s" && pwd)"
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require_safe_context

kubectl apply -f "${K8S_DIR}/namespace.yaml"
bash "${K8S_DIR}/../scripts/ensure-secret.sh"
for strategy in rolling blue-green canary ab-testing shadow; do
  echo "== ${strategy}"
  for f in "${K8S_DIR}/${strategy}"/*.yaml; do
    sed "s#your-dockerhub-username#${DOCKERHUB_USER}#g" "$f"
  done | kubectl apply -f -
done

echo "== waiting for all deployments"
kubectl -n aceest wait --for=condition=available deployment --all --timeout=300s
kubectl -n aceest get deployments,services,ingress -o wide
