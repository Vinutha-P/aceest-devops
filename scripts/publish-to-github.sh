#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# macOS / Linux version of publish-to-github.ps1.
# Push the repo to GitHub and merge every version through a real Pull Request,
# tagging each release (v1.1 ... v3.2.4) after its merge.
#
#   scripts/publish-to-github.sh https://github.com/<you>/aceest-devops.git
#   NO_JENKINS_PAUSE=1 scripts/publish-to-github.sh <repo-url>
#
# Requires: GitHub CLI logged in (gh auth login), an EMPTY GitHub repository.
# -----------------------------------------------------------------------------
set -euo pipefail
REPO_URL="${1:?usage: publish-to-github.sh <github-repo-url>}"
cd "$(dirname "${BASH_SOURCE[0]}")/.."

RELEASES=(
  "feature/v1.1-client-profile|v1.1|v1.1: Client profile and calorie estimation"
  "feature/v1.1.2-client-table-csv|v1.1.2|v1.1.2: Client list, CSV export and adherence chart"
  "feature/v2.0.1-sqlite-persistence|v2.0.1|v2.0.1: SQLite persistence and weekly progress"
  "bugfix/v2.1.2-validation-errors|v2.1.2|v2.1.2: Input validation and JSON error responses (bug fix)"
  "feature/v2.2.1-progress-chart|v2.2.1|v2.2.1: Weekly adherence progress chart"
  "feature/v2.2.4-workouts-metrics|v2.2.4|v2.2.4: Workouts, body metrics, BMI and summary"
  "feature/v3.0.1-production-k8s|v3.0.1|v3.0.1: Production readiness, Kubernetes strategies and CD stage"
  "feature/v3.1.2-auth-ai-pdf|v3.1.2|v3.1.2: Login, AI program generator and PDF report"
  "feature/v3.2.4-membership-roles|v3.2.4|v3.2.4: Membership tracking and role-based users"
  "docs/project-documentation||docs: README, submission guide, evidence checklist and report"
)

pause() { [ "${NO_JENKINS_PAUSE:-0}" = "1" ] || read -r -p "$1 " _; }

command -v gh >/dev/null || { echo "Install GitHub CLI (brew install gh / sudo apt install gh), then gh auth login"; exit 1; }
gh auth status >/dev/null

git remote | grep -qx origin || git remote add origin "$REPO_URL"
git push -u origin main
git push origin v1.0
for entry in "${RELEASES[@]}"; do
  git push -u origin "${entry%%|*}"
done

pause $'\nmain (v1.0) is on GitHub. Wait until Jenkins has built v1.0 successfully, then press Enter'

for entry in "${RELEASES[@]}"; do
  IFS='|' read -r branch tag title <<<"$entry"
  echo; echo "=== ${title} ==="
  gh pr create --base main --head "$branch" --title "$title" --body "## Summary
${title}

Implements the matching release of the original Tkinter app (see \`legacy_tkinter/\`).

## Checklist
- [x] Feature implemented on its own branch
- [x] Pytest tests added / updated
- [x] flake8 clean
- [x] GitHub Actions \"PR checks\" must pass before merge
- [x] Jenkins builds, scans (SonarQube), tests in container and publishes the image after merge"

  sleep 15   # let GitHub Actions register the checks
  gh pr checks "$branch" --watch --interval 15 \
    || { echo "PR checks failed for ${branch} - fix on GitHub, then re-run"; exit 1; }
  gh pr merge "$branch" --merge
  git fetch origin main

  if [ -n "$tag" ]; then
    git tag -a "$tag" "$(git rev-parse origin/main)" -m "Release ${tag}"
    git push origin "$tag"
    pause "Merged and tagged ${tag}. Wait for the Jenkins build of ${tag} to finish (green), then press Enter"
  fi
done

git checkout main && git pull origin main
echo; echo "Done. All versions merged through Pull Requests and tagged."
git log --oneline --graph --decorate -n 40
