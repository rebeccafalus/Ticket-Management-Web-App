# Kubernetes deployment

The manifests define three one-replica application deployments plus one
persistent PostgreSQL StatefulSet in the `ticket-management` namespace:
frontend, Python API, Go route service, and PostgreSQL. Every workload has
readiness and liveness checks, and the GitHub Actions workflow waits for every
rollout before running the smoke tests.

The image owner and tag are placeholders in the checked-in manifests. The
deployment workflow replaces them with the GitHub Container Registry owner and
commit SHA.

For local Minikube deployment, build the images in Minikube's Docker daemon and
provision the Go service Secret before applying the included overlay:

```bash
eval "$(minikube docker-env)"
docker compose -f infra/docker-compose.yml build
kubectl apply -f infra/k8s/namespace.yaml
kubectl -n ticket-management create secret generic route-go-auth \\
  --from-literal=TICKET_USERNAME="$TICKET_USERNAME" \\
  --from-literal=TICKET_PASSWORD="$TICKET_PASSWORD" \\
  --from-literal=ADMIN_USERNAME="$ADMIN_USERNAME" \\
  --from-literal=ADMIN_PASSWORD="$ADMIN_PASSWORD"
kubectl -n ticket-management delete deployment/ml service/ml --ignore-not-found
kubectl apply -k infra/k8s
```

Populate those four shell variables from a secret manager before running the
commands. Use distinct passwords of at least 32 characters. The credentials
are not stored in this repository; the Go service fails startup when the
Secret is absent or invalid, and deployment workflows check for it before
applying workloads.

The overlay is the root `infra/k8s/kustomization.yaml`; the GitHub Actions
workflow applies the plain manifests directly after replacing their image tags.
The delete command also removes the former ML workload when upgrading an
existing cluster.

The Python API runs the Alembic migration as an init container before starting.
The `postgres` Secret must provide `POSTGRES_DB`, `POSTGRES_USER`, and
`POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_PORT`. The local Secret in
`postgres.yaml` points to the in-cluster PostgreSQL service; for managed Azure
PostgreSQL, create the same Secret with the server FQDN as its host.

The frontend Service stays internal because the technician queue currently has
no sign-in. An operator with Kubernetes access can reach it securely through a
local port-forward:

```bash
kubectl -n ticket-management port-forward service/frontend 3000:80
```

Then open [http://localhost:3000](http://localhost:3000). This works with
cloud Kubernetes and Minikube without an ingress controller or public load
balancer. The frontend proxies ticket API calls internally, so the backend
does not need a public endpoint.