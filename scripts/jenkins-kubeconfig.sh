#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Give the Jenkins container access to Minikube.
#   1. connects the "jenkins" container to the "minikube" Docker network
#   2. writes jenkins/kubeconfig-minikube with the API server's in-network address
# Upload the generated file to Jenkins as a "Secret file" credential with ID: kubeconfig
# -----------------------------------------------------------------------------
set -euo pipefail
OUT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../jenkins" && pwd)/kubeconfig-minikube"

docker network connect minikube jenkins 2>/dev/null || echo "jenkins already on the minikube network"
MINIKUBE_IP="$(minikube ip)"

kubectl config view --minify --flatten --context=minikube \
  | sed "s#server: https://.*#server: https://${MINIKUBE_IP}:8443#" > "$OUT"

echo "Wrote ${OUT} (server https://${MINIKUBE_IP}:8443)"
echo "Testing from inside the Jenkins container..."
docker cp "$OUT" jenkins:/tmp/kubeconfig-test
docker exec jenkins kubectl --kubeconfig /tmp/kubeconfig-test get nodes
docker exec jenkins rm -f /tmp/kubeconfig-test
echo "OK - now upload ${OUT} to Jenkins: Manage Jenkins > Credentials > Secret file, ID 'kubeconfig'"
