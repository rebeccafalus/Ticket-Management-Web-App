# Kubernetes deployment

The manifests define the frontend, Python API, and Go route service in the
`ticket-management` namespace. Each deployment has readiness and liveness
probes, and the GitHub Actions workflow waits for every rollout before running
the smoke tests.

The image owner and tag are placeholders in the checked-in manifests. The
deployment workflow replaces them with the GitHub Container Registry owner and
commit SHA.