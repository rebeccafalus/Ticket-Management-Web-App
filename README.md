# Ticket Management Web App

This workspace is split into four repository areas:

- `frontend/` - web client
- `backend-py/` - Python API
- `ml/` - ML service
- `route-go/` - Go routing service
- `infra/` - local service orchestration

## Health endpoints

Run the services locally:

```bash
cd backend-py && python3 -m pip install -r requirements.txt && uvicorn app.main:app --port 8000
cd route-go && go run .
```

Then check:

```bash
curl http://localhost:8000/health
curl http://localhost:8080/health
```

Both endpoints return `{"status":"ok"}`.

## Prometheus monitoring

The Go routing service exposes Prometheus metrics at `/metrics`. The local
Compose stack starts Prometheus on [http://localhost:9090](http://localhost:9090)
and scrapes `route-go:8080/metrics` every 15 seconds:

```bash
docker compose -f infra/docker-compose.yml up --build
```

The Kubernetes manifests include a Prometheus deployment and service in the
`ticket-management` namespace. Access it locally with:

```bash
kubectl -n ticket-management port-forward service/prometheus 9090:9090
```

The ticket guide is protected by a session-based sign-in. For now, any
username containing `@un.org` is accepted. Configure `TICKET_PASSWORD` on the
Go service; the local Compose default is `ticket-management-dev`, which should
be replaced before sharing the service. Kubernetes reads the password from the
`route-go-auth` Secret in `infra/k8s/route-go-auth.yaml`.

An analytics dashboard is available at `/admin`. Sign in with username `adm`
and password `placeholder` to view guide request totals, service status, and
the Prometheus metrics link.

## Docker Compose

From the repository root:

```bash
docker compose -f infra/docker-compose.yml up --build
```

## CI/CD and security

The GitHub Actions workflows provide:

- Pull-request validation: Python and Go checks, Compose build, smoke tests, and Trivy filesystem scanning
- Required merge gates: configure `Pull request validation / validate` as a required status check in branch protection
- Image publishing: immutable SHA tags and `latest` tags in GitHub Container Registry
- Staging deployment: automatic deployment to Kubernetes after a successful `main` build, followed by rollout and smoke tests
- Kubernetes workload: one frontend pod, one Python API pod, one ML pod, and one Go pod
- PostgreSQL: one persistent StatefulSet pod named `postgres`
- Production deployment: paused behind the GitHub `production` Environment approval rule
- Security scanning: Trivy filesystem and image scans on pull requests, releases, and every Monday at 03:30 UTC

Configure these repository settings before enabling deployments:

1. Create `staging` and `production` GitHub Environments.
2. Add `KUBE_CONFIG_STAGING` to the `staging` environment and `KUBE_CONFIG_PRODUCTION` to the `production` environment. Each secret must contain the complete raw kubeconfig file, including its `apiVersion`, `clusters`, `users`, and `contexts` sections. Add required reviewers to `production`.
3. Protect `main` and require the `Pull request validation / validate` check before merging.
4. Grant the Actions workflow permission to write packages, and make the GHCR packages readable by the target clusters.

Kubernetes manifests are in `infra/k8s/`. The deployment workflow replaces the placeholder registry owner and image tag before applying them. The desired workload is five pods: `frontend`, `backend-py`, `ml`, `route-go`, and `postgres`, each with one replica.

Azure AKS and managed PostgreSQL provisioning is documented in [infra/terraform/README.md](infra/terraform/README.md). In Azure, PostgreSQL is managed outside Kubernetes, so deploy only the four application workloads and do not apply the local PostgreSQL StatefulSet.

The Terraform deployment defaults to West Central US because this subscription
has PostgreSQL provisioning restrictions in East US.

If the existing East US resource group must be preserved, use the separate
`staging-west` Terraform workspace described in
[infra/terraform/README.md](infra/terraform/README.md) rather than applying
the replacement plan from the `default` workspace.

## Rollback

Every deployment uses an immutable commit SHA image tag. To roll back a failed staging or production release, identify the previous revision and run:

```bash
kubectl -n ticket-management rollout history deployment/frontend
kubectl -n ticket-management rollout undo deployment/frontend --to-revision=<revision>
kubectl -n ticket-management rollout undo deployment/backend-py --to-revision=<revision>
kubectl -n ticket-management rollout undo deployment/ml --to-revision=<revision>
kubectl -n ticket-management rollout undo deployment/route-go --to-revision=<revision>
kubectl -n ticket-management rollout history statefulset/postgres
kubectl -n ticket-management rollout undo statefulset/postgres --to-revision=<revision>
kubectl -n ticket-management rollout status statefulset/postgres --timeout=180s
kubectl -n ticket-management rollout status deployment/frontend --timeout=180s
kubectl -n ticket-management rollout status deployment/backend-py --timeout=180s
kubectl -n ticket-management rollout status deployment/ml --timeout=180s
kubectl -n ticket-management rollout status deployment/route-go --timeout=180s
```

Run the smoke tests from a pod in the namespace after rollback, then open a follow-up pull request for the permanent fix. Do not delete the namespace during rollback because it removes the service history and configuration.
