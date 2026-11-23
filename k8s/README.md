# Kubernetes manifests

Namespace `aceest`. Each folder is one deployment strategy. A single ingress (no host)
exposes all of them under path prefixes, so **one URL** serves every strategy (localhost via
`minikube tunnel`, an ngrok URL, or a cloud load balancer).

| Folder | Path | Objects |
|---|---|---|
| `rolling/` | `/rolling`, `/` | Deployment (3 replicas, RollingUpdate maxSurge 1 / maxUnavailable 0), Service, Ingress |
| `blue-green/` | `/bluegreen` | Deployments `aceest-blue`, `aceest-green`; Services `aceest-bluegreen` (live) + `aceest-bluegreen-preview` |
| `canary/` | `/canary` | Deployments stable (3) + canary (1); stable Ingress + canary Ingress (`canary-weight: 20`) |
| `ab-testing/` | `/ab` | Variant A + B; canary Ingress routed by header `X-Variant: B` / cookie `ab_variant=always` |
| `shadow/` | `/shadow` | Primary + shadow; Ingress `mirror-target` sends a copy of each request to the shadow |

Images use the placeholder `your-dockerhub-username/aceest-fitness:<tag>`. The scripts replace
it with `$DOCKERHUB_USER`, so you never have to edit these files:

```bash
DOCKERHUB_USER=<you> scripts/bootstrap-k8s.sh            # first-time create of all strategies
scripts/deploy.sh <strategy> <you>/aceest-fitness:<tag>  # what Jenkins runs
scripts/rollback.sh <strategy>                           # manual rollback
```

All pods: non-root (UID 10001), read-only root filesystem, all capabilities dropped,
seccomp `RuntimeDefault`, CPU/memory requests and limits, liveness `/health`,
readiness `/ready`, and a `preStop` delay for graceful shutdown. Secrets
(`ACEEST_SECRET_KEY`, `ACEEST_ADMIN_PASSWORD`) come from the `aceest-secrets` Secret created by
`scripts/ensure-secret.sh` (never committed to Git).

> Each pod uses its own SQLite file on an `emptyDir` volume, which is fine for this demo.
> A production setup would move data to a managed database (PostgreSQL) so all replicas share
> state. See the report's "Challenges" section.
