# Step-by-step: from this folder to a complete submission

Follow the phases in order. Commands marked **PowerShell** run in a normal PowerShell
window. Commands marked **Git Bash** run in Git Bash (installed with Git for Windows).
Always run them from the project folder:

```
cd D:\DevOps-V\part-2\aceest-devops
```

> **On macOS or Ubuntu?** Every **Git Bash** command works unchanged in the normal Terminal.
> For the **PowerShell** commands, use the equivalents in
> [macOS and Ubuntu commands](#macos-and-ubuntu-commands) at the end of this guide.

Placeholders: `<you>` = your Docker Hub username, `<gh-user>` = your GitHub username.

> At every step marked **(EVIDENCE)**, take a screenshot and save it in
> `docs/evidence/` (see [EVIDENCE-CHECKLIST.md](EVIDENCE-CHECKLIST.md)). Last time marks were
> lost for missing execution evidence, so don't skip these.

---

## Phase 0: One-time installs and accounts (about 20 min)

| Tool | Check | Install |
|---|---|---|
| Docker Desktop | `docker version` | already installed |
| kubectl, minikube | `kubectl version --client`, `minikube version` | already installed |
| Git + Git Bash | `git --version` | already installed |
| GitHub CLI | `gh --version` | **PowerShell:** `winget install GitHub.cli` (then reopen PowerShell) |
| ngrok (optional, for a public URL) | `ngrok version` | `winget install ngrok.ngrok` + free account token |

Accounts:
1. **GitHub**: sign in, then run `gh auth login` (PowerShell) and pick GitHub.com → HTTPS → login with browser.
2. **Docker Hub**: create a **public** repository named `aceest-fitness`.
   Then go to Account settings → Personal access tokens → **Generate new token** (Read & Write). Copy it.

## Phase 1: Check the project locally (5 min)

**PowerShell**
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pytest --cov=aceest --cov-report=term-missing --cov-report=html:docs/evidence/coverage-html
flake8
```
Expected: `238 passed`, coverage `100%`. **(EVIDENCE)** screenshot of the test + coverage output.

Optional: try the app with `$env:ACEEST_ADMIN_PASSWORD="ChangeMe123"; python ACEest_Fitness.py`
and open http://localhost:5000.

## Phase 2: Create the GitHub repository (2 min)

On GitHub: **New repository** → name `aceest-devops` → **Public** → **do NOT** add a README,
.gitignore or licence (it must be empty).

## Phase 3: Start Jenkins and SonarQube (15 min)

**PowerShell**
```powershell
docker compose -f jenkins/docker-compose.yml up -d --build
```
The first build downloads Jenkins, the plugins and SonarQube, which takes a few minutes.

### 3a. SonarQube (http://localhost:9000)
1. Log in with `admin` / `admin` and set a new password.
2. **My Account → Security → Generate token**: name `jenkins`, type *Global Analysis Token*. Copy it.
3. **Administration → Configuration → Webhooks → Create**:
   name `jenkins`, URL `http://jenkins:8080/sonarqube-webhook/`
   (Jenkins needs this to receive the quality-gate result).

### 3b. Jenkins (http://localhost:8080)
1. Get the unlock password:
   `docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword`
2. Choose **Install suggested plugins** (the pipeline plugins are already baked into the image),
   then create your admin user.
3. **Manage Jenkins → System**:
   - **Global properties → Environment variables → Add**: Name `DOCKERHUB_USER`, Value `<you>`
   - **SonarQube servers → Add SonarQube**: Name **`SonarQube`** (exactly), URL
     `http://sonarqube:9000`, Server authentication token → **Add → Jenkins → Secret text**
     (paste the SonarQube token, ID `sonarqube-token`) → select it. Tick
     *Environment variables*. **Save.**
4. **Manage Jenkins → Credentials → System → Global → Add credentials**:
   - *Username with password*: username `<you>`, password = Docker Hub access token, **ID `dockerhub`**

## Phase 4: Start Minikube and connect Jenkins to it (10 min)

**PowerShell**
```powershell
minikube start --driver=docker --cpus=4 --memory=4g
minikube addons enable ingress
kubectl config current-context        # must print: minikube
kubectl get nodes
```

> **Safety:** the deploy scripts refuse to run unless the kubectl context is `minikube`, so a
> work/cloud cluster (e.g. an EKS context) can never be changed by accident. After the
> assignment, switch back with `kubectl config use-context <your-other-context>`.
> Docker Desktop needs about 8 GB RAM in total for Minikube (4 GB) + Jenkins + SonarQube.

**Git Bash**
```bash
scripts/jenkins-kubeconfig.sh
```
This connects the Jenkins container to Minikube's network, writes
`jenkins/kubeconfig-minikube` (it is git-ignored) and tests `kubectl get nodes` from inside
Jenkins.

Jenkins → **Manage Jenkins → Credentials → Add credentials → Secret file**: upload
`jenkins/kubeconfig-minikube`, **ID `kubeconfig`**.

Choose the admin password for the app now (otherwise a random one is generated):

**Git Bash**
```bash
ACEEST_ADMIN_PASSWORD='ChangeMe123' scripts/ensure-secret.sh
```

## Phase 5: Publish to GitHub with Pull Requests and let Jenkins build every version (60–90 min, mostly waiting)

This phase produces the branching / pull-request / Jenkins-run evidence.

**PowerShell**
```powershell
.\scripts\publish-to-github.ps1 -RepoUrl https://github.com/<gh-user>/aceest-devops.git
```
(If PowerShell blocks the script: `Set-ExecutionPolicy -Scope Process Bypass` first.)

The script pushes `main` (v1.0) and all version branches, then **pauses**. While it waits:

1. In Jenkins: **New Item** → name `aceest-fitness` → **Pipeline** → OK.
   - *Pipeline → Definition*: **Pipeline script from SCM** → SCM **Git** →
     Repository URL `https://github.com/<gh-user>/aceest-devops.git` →
     Branch `*/main` → Script Path `Jenkinsfile` → **Save**.
2. Click **Build Now** once. This first build registers the `pollSCM` trigger and the build
   parameters. Wait for it to turn green (v1.0).
3. Go back to PowerShell and press **Enter**.

For each version the script then opens a PR, waits for the GitHub Actions check, merges it,
tags it (`v1.1`, `v1.1.2`, …) and pauses again. **Each time, wait until Jenkins has started
and finished the build of that version (it polls GitHub every ~2 minutes), then press Enter.**
That way every version gets its own Jenkins run and its own image on Docker Hub.

From **v3.0.1** onwards the Jenkins *Deploy to Kubernetes* stage runs automatically (rolling
update).

**(EVIDENCE)** GitHub *Pull requests → Closed* list, one merged PR showing the green check,
the *Network* graph (Insights → Network), the tags list, the Jenkins job page with all the green
builds, the stage view of one build, the Docker Hub *Tags* page.

> If something fails: open the failed Jenkins stage log, fix it, and re-run the script. It
> stops at the first failed step, so already-merged versions are not touched. If a version
> was skipped in Jenkins (two merges inside one poll), run
> `DOCKERHUB_USER=<you> scripts/build-all-versions.sh` in Git Bash to push every tag's image.

Also create the rollback job: **New Item** → `aceest-rollback` → Pipeline → *Pipeline script
from SCM* (same repository, branch `*/main`), Script Path **`jenkins/Jenkinsfile.rollback`**.

## Phase 6: Deploy every strategy (20 min)

In Jenkins open `aceest-fitness` → **Build with Parameters** and run it once for each
`DEPLOY_STRATEGY`:

1. `blue-green`
2. `canary` (CANARY_WEIGHT `20`)
3. `ab`
4. `shadow`

(`rolling` already ran automatically.) The first run of each strategy creates both the current
side (v3.1.2) and the new side, then deploys the new build, smoke-tests it and switches or
weights traffic.

Check the cluster: **PowerShell** `kubectl -n aceest get deploy,svc,ingress,pods -o wide`
**(EVIDENCE)**

## Phase 7: Show the strategies working, and rollback (20 min)

Open a **second PowerShell window as Administrator** and leave it running:
```powershell
minikube tunnel
```

Now the cluster is reachable at **http://127.0.0.1**:

| Open in a browser / curl | Shows |
|---|---|
| http://127.0.0.1/ | dashboard (rolling deployment) |
| http://127.0.0.1/rolling/version | rolling deployment version |
| http://127.0.0.1/bluegreen/version | live colour only |
| http://127.0.0.1/canary/version (refresh many times) | mostly `stable`, sometimes `canary` |
| `curl -H "X-Variant: B" http://127.0.0.1/ab/version` | variant B (without header: A) |
| http://127.0.0.1/shadow/version | always primary; the shadow receives a copy |

**Git Bash**, to record all of it into a file:
```bash
scripts/demo-strategies.sh            # -> docs/evidence/strategies-<date>.txt
```

### Rollback evidence
1. **Automatic rollback** (a deliberately broken image). **Git Bash**:
   ```bash
   ROLLOUT_TIMEOUT=60s scripts/deploy.sh rolling <you>/aceest-fitness:does-not-exist
   ```
   The rollout fails (image not found), the script prints `ROLLING BACK` and the old version
   keeps serving. **(EVIDENCE)** terminal output plus `kubectl -n aceest rollout history deployment/aceest-rolling`.
2. **Manual rollback job**: Jenkins `aceest-rollback` → Build with Parameters → `blue-green`.
   Then http://127.0.0.1/bluegreen/version shows the previous colour/version. **(EVIDENCE)**
3. **Canary promote** (optional): `aceest-fitness` → Build with Parameters → `canary-promote`.

## Phase 8: Endpoint URL for submission

Minikube only runs on your laptop. To submit a URL the evaluator can open:

**PowerShell** (keep `minikube tunnel` running in the other window)
```powershell
ngrok config add-authtoken <your-ngrok-token>   # once
ngrok http 80
```
ngrok prints `https://xxxx.ngrok-free.app`. Every strategy is a path on that one URL:
`/`, `/rolling/version`, `/bluegreen/version`, `/canary/version`, `/ab/version`, `/shadow/version`.
The URL only works while your laptop, minikube tunnel and ngrok are running, so mention that in
the submission and keep them running during the evaluation window. Check with your instructor
whether a local URL plus screenshots and the demo output is acceptable instead.

## Phase 9: SonarQube report

**Git Bash**
```bash
SONAR_TOKEN=<sonarqube-token> scripts/sonar-report.sh   # -> docs/evidence/sonarqube-report.md
```
**(EVIDENCE)** screenshot of the SonarQube project dashboard (Quality Gate **Passed**).

## Phase 10: Commit the evidence through one more Pull Request

**PowerShell**
```powershell
git checkout main
git pull
git checkout -b docs/execution-evidence
git add docs/evidence
git commit -m "docs: execution evidence (tests, pipeline, SonarQube, deployments)"
git push -u origin docs/execution-evidence
gh pr create --base main --title "docs: execution evidence" --body "Screenshots and command outputs from the running pipeline and cluster."
gh pr merge --merge
```

## Phase 11: Report and submission

1. Open `docs/ACEest_DevOps_Report.docx`, add your name/ID on the cover, paste 4–6 key
   screenshots where marked, and export it to PDF if your portal needs PDF.
2. Submit:
   - GitHub repository: `https://github.com/<gh-user>/aceest-devops`
   - Docker Hub repository: `https://hub.docker.com/r/<you>/aceest-fitness/tags`
   - Endpoint URL (ngrok) with the path list from Phase 8
   - The report (2–3 pages)
   - The project folder / zip if requested (the repository already contains the Flask app and
     versions, Jenkinsfile, Dockerfile, Kubernetes manifests, tests and SonarQube report)

## Troubleshooting

| Problem | Fix |
|---|---|
| Jenkins: `docker: permission denied` | the compose file runs Jenkins as root; recreate with `docker compose -f jenkins/docker-compose.yml up -d --force-recreate` |
| Quality Gate stage waits forever | SonarQube webhook missing or wrong URL (Phase 3a step 3) |
| `DOCKERHUB_USER is not set` | Phase 3b step 3 (Global properties) |
| Deploy stage: `connection refused` to Kubernetes | Minikube restarted, so its IP may change: re-run `scripts/jenkins-kubeconfig.sh` and re-upload the credential |
| Pods `ImagePullBackOff` | the image tag isn't on Docker Hub yet, or the repository is private |
| http://127.0.0.1 not responding | `minikube tunnel` must be running in an **Administrator** window |
| SonarQube container exits | give Docker Desktop at least 8 GB RAM (Settings → Resources) |
| Script says `[safety] kubectl context is ...` | `kubectl config use-context minikube` |

---

## macOS and Ubuntu commands

Everything in `scripts/*.sh`, `kubectl`, `minikube`, `docker` and `git` is identical on all three
systems. Only these steps differ.

### Phase 0: installs

**macOS** (Homebrew, https://brew.sh):
```bash
brew install --cask docker            # Docker Desktop, then start it from Applications
brew install git python@3.12 kubectl minikube gh
brew install ngrok/ngrok/ngrok        # optional, for the public URL
gh auth login
```

**Ubuntu 22.04 / 24.04**:
```bash
sudo apt update && sudo apt install -y git python3 python3-venv python3-pip curl gh
curl -fsSL https://get.docker.com | sudo sh                    # Docker Engine + compose plugin
sudo usermod -aG docker "$USER" && newgrp docker                # use docker without sudo
curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install kubectl /usr/local/bin/kubectl
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
sudo snap install ngrok                                         # optional
gh auth login
```

### Command equivalents

| Step | Windows (PowerShell) | macOS / Ubuntu (Terminal) |
|---|---|---|
| Go to project | `cd D:\DevOps-V\part-2\aceest-devops` | `cd ~/aceest-devops` (wherever you copied it) |
| Create venv | `python -m venv .venv` | `python3 -m venv .venv` |
| Activate venv | `.venv\Scripts\activate` | `source .venv/bin/activate` |
| Set a variable | `$env:ACEEST_ADMIN_PASSWORD="ChangeMe123"` | `export ACEEST_ADMIN_PASSWORD=ChangeMe123` |
| Run the app | `python ACEest_Fitness.py` | `python3 ACEest_Fitness.py` |
| Tests / lint | `pytest --cov=aceest` · `flake8` | same |
| Jenkins + SonarQube | `docker compose -f jenkins/docker-compose.yml up -d --build` | same |
| Jenkins unlock password | `docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword` | same |
| Minikube | `minikube start --driver=docker --cpus=4 --memory=4g` | same |
| Publish with PRs (Phase 5) | `.\scripts\publish-to-github.ps1 -RepoUrl <url>` | `scripts/publish-to-github.sh <url>` |
| Reach the cluster (Phase 7) | `minikube tunnel` (Administrator window), then `http://127.0.0.1` | **macOS:** `minikube tunnel` (asks for your sudo password), then `http://127.0.0.1` · **Ubuntu:** no tunnel needed, use `http://$(minikube ip)` |
| Strategy demo | `scripts/demo-strategies.sh` (Git Bash) | macOS: `scripts/demo-strategies.sh` · Ubuntu: `BASE_URL=http://$(minikube ip) scripts/demo-strategies.sh` |
| Public URL | `ngrok http 80` | macOS: `ngrok http 80` · Ubuntu: `ngrok http $(minikube ip):80` |
| Open report | Word | Word / Pages / LibreOffice Writer |

If the scripts aren't executable after copying the folder: `chmod +x scripts/*.sh`.

**Apple Silicon (M1/M2/M3) note:** images built on the Mac are `arm64`. That's fine for your
own Minikube. If the evaluator might run them on an Intel/AMD machine, publish multi-arch images:
```bash
docker buildx create --use
docker buildx build --platform linux/amd64,linux/arm64 --target runtime \
  -t <you>/aceest-fitness:3.2.4 --push .
```
