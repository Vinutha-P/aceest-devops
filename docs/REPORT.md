# ACEest Fitness & Gym: CI/CD Implementation Report

**Course:** Introduction to DevOps (CSIZG514/SEZG514), Assignment 2
**Repository:** `https://github.com/<gh-user>/aceest-devops` · **Images:** `https://hub.docker.com/r/<you>/aceest-fitness`

## 1. Objective and scope

ACEest's product was provided as ten incremental **Tkinter desktop** releases (1.0 → 3.2.4).
Desktop GUIs cannot be containerised, tested over HTTP or deployed to Kubernetes, so each
release was re-implemented as a **Flask web application** with the same features. Every
version was then delivered through an automated pipeline: Git/GitHub → Jenkins → Pytest →
SonarQube → Docker Hub → Kubernetes, with five deployment strategies and automatic rollback.

## 2. CI/CD architecture overview

```
Developer ─► feature branch ─► merge to main ─► GitHub Actions checks (lint, tests, docker)
                                   │
                                   ▼
GitHub main ──pollSCM (2 min)──► Jenkins pipeline
  Checkout ─► Setup ─► flake8 ─► Pytest + coverage ─► SonarQube scan ─► Quality Gate
  ─► Docker build ─► Pytest inside container + smoke test ─► Push to Docker Hub
  ─► Deploy to Kubernetes (strategy, smoke test, auto-rollback) ─► Archive artifacts
                                   ▼
Minikube (namespace aceest) ─ ingress-nginx, one URL:
  /rolling  /bluegreen  /canary (20 %)  /ab (header/cookie)  /shadow (mirrored)
```

| Layer | Implementation |
|---|---|
| Application | Flask app factory, 13 modules (programs, clients, tracking, auth, AI program, PDF, membership, users…), SQLite with in-place migrations, gunicorn |
| Version control | `main` + one branch per release (`feature/…`, `bugfix/…`), merged into `main` in release order, tags `v1.0`…`v3.2.4`, conventional commit messages |
| Testing | 238 Pytest tests, 100 % line coverage; run locally, in GitHub Actions, in Jenkins and **inside the container** |
| Quality | flake8 + SonarQube (Python analysis, coverage import, quality gate enforced by `waitForQualityGate`) |
| Build | Multi-stage Dockerfile: `test` stage (runs pytest) and slim **non-root** `runtime` stage with healthcheck |
| Registry | Docker Hub `aceest-fitness:<version>`, `<version>-b<build>`, `latest`; all ten versions |
| Deployment | Kubernetes manifests per strategy; `scripts/deploy.sh` used by the Jenkins Deploy stage |
| Rollback | automatic in every strategy plus a separate Jenkins rollback job |

**Deployment strategies:** *Rolling update* (maxSurge 1 / maxUnavailable 0, readiness-gated:
zero downtime). *Blue-green* (new colour deployed and smoke-tested through a preview Service,
then the live Service selector is switched; the old colour stays as an instant rollback target).
*Canary* (ingress-nginx weighted canary, 20 %, with a promote action). *A/B testing*
(header `X-Variant: B` / cookie routing to variant B). *Shadow* (ingress-nginx `mirror-target`
duplicates live traffic to the new version; users only see the primary). Every response carries
`X-App-Version` / `X-Deployment-Track` headers, so the traffic split can be observed.

## 3. Challenges and mitigation

| Challenge | Mitigation |
|---|---|
| Provided code was a desktop (Tkinter) app, not a web app | Re-implemented each release as Flask endpoints, one branch per version; originals kept in `legacy_tkinter/` as the specification |
| Versions 2.1.2 and 3.0.1 were byte-identical to 2.0.1 and 2.2.4 | Used them as a **bug-fix release** (validation, JSON errors) and a **production-hardening release** (probes, gunicorn, Kubernetes) |
| Desktop app stored `admin/admin` in plain text | Salted password hashes, admin password from a Kubernetes Secret, signed expiring tokens shared across replicas |
| Schema changed between versions (the desktop app dropped tables) | In-place `ALTER TABLE` migrations, tested with a v2.0 database; fixed a race between gunicorn workers (preload + duplicate-column tolerance) |
| Several strategies needed on one endpoint URL | Path-prefix ingress plus a small WSGI `PrefixMiddleware` (no URL rewriting, so nginx traffic mirroring still works) |
| Jenkins in Docker needed Docker, kubectl and sonar-scanner and had to reach Minikube | Custom Jenkins image, host Docker socket, Jenkins attached to the `minikube` network with a generated kubeconfig credential |
| Windows line endings broke shell scripts inside Linux containers | `.gitattributes` forces LF for all files except `.ps1` |
| SonarQube quality gate would flag security hotspots | Literal SQL statements (no string-built SQL), `SystemRandom`, no hard-coded credentials |
| Re-pushing the same tag does not trigger a Kubernetes rollout | Jenkins deploys the unique tag `<version>-b<build>` |
| Risk of deploying to the wrong cluster (a work EKS context was active on the laptop) | Scripts refuse to run unless the kubectl context is `minikube` (explicit override for cloud) |
| SQLite is per pod, so replicas don't share data | Acceptable for the demo; documented; production would use a managed PostgreSQL behind the same API |

## 4. Key automation outcomes

| Outcome | Result |
|---|---|
| Versions delivered | 10 (v1.0 → v3.2.4), each on its own branch and tag, with its own Docker Hub image |
| Test suite | 238 tests, 100 % coverage, executed 4× per change (local, GitHub Actions, Jenkins, container) |
| Pipeline | 11 stages, triggered automatically by SCM polling; build time ≈ `<fill in from Jenkins>` min |
| Quality gate | SonarQube gate **Passed** (`<bugs / vulnerabilities / smells from sonarqube-report.md>`) |
| Image | non-root (UID 10001), read-only root filesystem in Kubernetes, ≈ 260 MB |
| Deployments | 5 strategies live at one URL; zero-downtime rolling updates |
| Rollback | automatic on failed rollout or smoke test (demonstrated with a non-existent image); manual job in Jenkins |
| Evidence | `docs/evidence/`: screenshots, strategy demo output, SonarQube report, coverage HTML |

## 5. Conclusion

The project turns a manually-run desktop tool into a continuously delivered web service. Every
change is version-controlled on its own branch, automatically tested, scanned
for quality and packaged as an immutable image. It reaches users through a controlled strategy
and can be reverted in seconds. The same pipeline can target a cloud cluster (AKS, EKS or GKE) by
changing only the kubeconfig credential.
