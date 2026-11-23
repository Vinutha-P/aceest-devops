#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Create the "aceest-secrets" Secret once (random values unless provided).
#   ACEEST_ADMIN_PASSWORD=MyPass123 scripts/ensure-secret.sh
# Read the admin password later with:
#   kubectl -n aceest get secret aceest-secrets \
#     -o jsonpath='{.data.ACEEST_ADMIN_PASSWORD}' | base64 -d
# -----------------------------------------------------------------------------
set -euo pipefail
NS="${NAMESPACE:-aceest}"
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require_safe_context

random_hex() { head -c "$1" /dev/urandom | od -An -tx1 | tr -d ' \n'; }

kubectl get namespace "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS"
if kubectl -n "$NS" get secret aceest-secrets >/dev/null 2>&1; then
  echo "[secret] aceest-secrets already exists - leaving it unchanged"
  exit 0
fi

ADMIN_PASSWORD="${ACEEST_ADMIN_PASSWORD:-$(random_hex 8)}"
kubectl -n "$NS" create secret generic aceest-secrets \
  --from-literal=ACEEST_SECRET_KEY="$(random_hex 32)" \
  --from-literal=ACEEST_ADMIN_PASSWORD="$ADMIN_PASSWORD"
echo "[secret] created aceest-secrets - admin login: admin / ${ADMIN_PASSWORD}"
