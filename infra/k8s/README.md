# Kubernetes deployment

The manifests define four one-replica application deployments plus one
persistent PostgreSQL StatefulSet in the `ticket-management` namespace:
frontend, Python API, ML, Go route service, and PostgreSQL. Every workload has
readiness and liveness checks, and the GitHub Actions workflow waits for every
rollout before running the smoke tests.

The image owner and tag are placeholders in the checked-in manifests. The
deployment workflow replaces them with the GitHub Container Registry owner and
commit SHA.

For local Minikube deployment, build the images in Minikube's Docker daemon and
apply the included overlay:

```bash
eval "$(minikube docker-env)"
docker compose -f infra/docker-compose.yml build
kubectl apply -k infra/k8s
```

The overlay is the root `infra/k8s/kustomization.yaml`; the GitHub Actions
workflow applies the plain manifests directly after replacing their image tags.