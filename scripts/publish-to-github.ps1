<#
.SYNOPSIS
  Push the repository to GitHub and merge every version through a real Pull Request,
  tagging each release (v1.1 ... v3.2.4) after its merge.

.DESCRIPTION
  main already contains v1.0 (tag v1.0). Each later version lives on its own branch,
  stacked on the previous one. For every branch, in order, this script:
    1. opens a Pull Request into main (GitHub CLI)
    2. waits for the "PR checks" GitHub Actions workflow to pass
    3. merges the PR with a merge commit (branch kept as history)
    4. tags the merge commit (v1.1, v1.1.2, ...) and pushes the tag
    5. (default) pauses so Jenkins can build and push that version's image

  Prerequisites: GitHub CLI installed and logged in (winget install GitHub.cli; gh auth login),
  an EMPTY GitHub repository, and Jenkins already polling it (see docs/SUBMISSION-GUIDE.md).

.EXAMPLE
  .\scripts\publish-to-github.ps1 -RepoUrl https://github.com/<you>/aceest-devops.git
.EXAMPLE
  .\scripts\publish-to-github.ps1 -RepoUrl https://github.com/<you>/aceest-devops.git -NoJenkinsPause
#>
param(
    [Parameter(Mandatory = $true)][string]$RepoUrl,
    [switch]$NoJenkinsPause
)

$ErrorActionPreference = "Stop"

$Releases = @(
    @{ Branch = "feature/v1.1-client-profile";       Tag = "v1.1";   Title = "v1.1: Client profile and calorie estimation" },
    @{ Branch = "feature/v1.1.2-client-table-csv";   Tag = "v1.1.2"; Title = "v1.1.2: Client list, CSV export and adherence chart" },
    @{ Branch = "feature/v2.0.1-sqlite-persistence"; Tag = "v2.0.1"; Title = "v2.0.1: SQLite persistence and weekly progress" },
    @{ Branch = "bugfix/v2.1.2-validation-errors";   Tag = "v2.1.2"; Title = "v2.1.2: Input validation and JSON error responses (bug fix)" },
    @{ Branch = "feature/v2.2.1-progress-chart";     Tag = "v2.2.1"; Title = "v2.2.1: Weekly adherence progress chart" },
    @{ Branch = "feature/v2.2.4-workouts-metrics";   Tag = "v2.2.4"; Title = "v2.2.4: Workouts, body metrics, BMI and summary" },
    @{ Branch = "feature/v3.0.1-production-k8s";     Tag = "v3.0.1"; Title = "v3.0.1: Production readiness, Kubernetes strategies and CD stage" },
    @{ Branch = "feature/v3.1.2-auth-ai-pdf";        Tag = "v3.1.2"; Title = "v3.1.2: Login, AI program generator and PDF report" },
    @{ Branch = "feature/v3.2.4-membership-roles";   Tag = "v3.2.4"; Title = "v3.2.4: Membership tracking and role-based users" },
    @{ Branch = "docs/project-documentation";        Tag = "";       Title = "docs: README, submission guide, evidence checklist and report" }
)

function Invoke-Checked {
    param([string]$Description, [scriptblock]$Command)
    Write-Host "-> $Description" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "Failed: $Description (exit $LASTEXITCODE)" }
}

# ---------- prerequisites ----------
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI not found. Install it: winget install GitHub.cli  then run: gh auth login"
}
gh auth status | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Run 'gh auth login' first." }

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

# ---------- push main (v1.0) and all branches ----------
$remotes = git remote
if ($remotes -notcontains "origin") {
    Invoke-Checked "add remote origin" { git remote add origin $RepoUrl }
}
Invoke-Checked "push main + tag v1.0" { git push -u origin main }
Invoke-Checked "push tag v1.0" { git push origin v1.0 }
foreach ($r in $Releases) {
    Invoke-Checked "push $($r.Branch)" { git push -u origin $r.Branch }
}

if (-not $NoJenkinsPause) {
    Read-Host "`nmain (v1.0) is on GitHub. Wait until Jenkins has built v1.0 successfully, then press Enter"
}

# ---------- one Pull Request per version ----------
foreach ($r in $Releases) {
    $body = @"
## Summary
$($r.Title)

Implements the matching release of the original Tkinter app (see ``legacy_tkinter/``) as part of
the Flask web application. See the commit messages for the detailed change list.

## Checklist
- [x] Feature implemented on its own branch
- [x] Pytest tests added / updated (``pytest --cov=aceest``)
- [x] flake8 clean
- [x] GitHub Actions "PR checks" (lint, tests, Docker build) must pass before merge
- [x] Jenkins builds, scans (SonarQube), tests in container and publishes the image after merge
"@
    Write-Host "`n=== $($r.Title) ===" -ForegroundColor Yellow
    Invoke-Checked "create PR" {
        gh pr create --base main --head $r.Branch --title $r.Title --body $body
    }

    Start-Sleep -Seconds 15   # give GitHub Actions time to register the checks
    Write-Host "-> waiting for PR checks (GitHub Actions)..." -ForegroundColor Cyan
    gh pr checks $r.Branch --watch --interval 15
    if ($LASTEXITCODE -ne 0) {
        throw "PR checks failed for $($r.Branch) - open the PR on GitHub, fix, then re-run from this branch."
    }

    Invoke-Checked "merge PR" { gh pr merge $r.Branch --merge }
    Invoke-Checked "fetch main" { git fetch origin main }

    if ($r.Tag) {
        $sha = (git rev-parse origin/main).Trim()
        Invoke-Checked "tag $($r.Tag)" { git tag -a $r.Tag $sha -m "Release $($r.Tag)" }
        Invoke-Checked "push tag $($r.Tag)" { git push origin $r.Tag }
        if (-not $NoJenkinsPause) {
            Read-Host "Merged and tagged $($r.Tag). Wait for the Jenkins build of $($r.Tag) to finish (green), then press Enter"
        }
    }
}

Invoke-Checked "update local main" { git checkout main }
Invoke-Checked "pull main" { git pull origin main }
Write-Host "`nDone. All versions merged through Pull Requests and tagged." -ForegroundColor Green
git log --oneline --graph --decorate -n 40
