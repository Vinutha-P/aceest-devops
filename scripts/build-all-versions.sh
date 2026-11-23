#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Build (and push) a Docker image for EVERY released version, straight from the
# Git tags v1.0 ... v3.2.4, so Docker Hub holds all versions of the app.
#   DOCKERHUB_USER=myuser scripts/build-all-versions.sh          (build + push)
#   PUSH=0 DOCKERHUB_USER=myuser scripts/build-all-versions.sh   (build only)
# -----------------------------------------------------------------------------
set -euo pipefail
: "${DOCKERHUB_USER:?set DOCKERHUB_USER to your Docker Hub username}"
PUSH="${PUSH:-1}"
REPO="${DOCKERHUB_USER}/aceest-fitness"
cd "$(dirname "${BASH_SOURCE[0]}")/.."

tags=$(git tag -l 'v*' --sort=v:refname)
[ -n "$tags" ] || { echo "No v* tags found - run 'git fetch --tags' first"; exit 1; }

latest=""
for tag in $tags; do
  version="${tag#v}"
  echo "=============== ${tag} -> ${REPO}:${version}"
  # build from the exact files of that tag (no checkout needed)
  git archive --format=tar "$tag" \
    | docker build --target runtime --build-arg APP_VERSION="$version" -t "${REPO}:${version}" -
  [ "$PUSH" = "1" ] && docker push "${REPO}:${version}"
  latest="$version"
done

docker tag "${REPO}:${latest}" "${REPO}:latest"
[ "$PUSH" = "1" ] && docker push "${REPO}:latest"
echo
docker images "${REPO}" --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}'
