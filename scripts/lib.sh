#!/usr/bin/env bash
# Shared helpers for the deployment scripts (sourced, not executed).

# Refuse to touch any cluster other than Minikube unless explicitly allowed.
# Protects against deploying into a work/cloud cluster that happens to be the
# current kubectl context. Use ALLOW_ANY_CONTEXT=1 for AKS/EKS/GKE on purpose.
require_safe_context() {
  local ctx
  ctx="$(kubectl config current-context 2>/dev/null || true)"
  if [ "${ALLOW_ANY_CONTEXT:-0}" != "1" ] && [ "$ctx" != "minikube" ]; then
    echo "[safety] kubectl context is '${ctx:-<none>}', expected 'minikube'." >&2
    echo "[safety] Run 'kubectl config use-context minikube' first," >&2
    echo "[safety] or set ALLOW_ANY_CONTEXT=1 if you really mean to deploy to '${ctx}'." >&2
    exit 1
  fi
}
