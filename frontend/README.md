# Frontend

The service desk is a static HTML client served by Nginx. It reads and writes
tickets through the same-origin `/api/` path; Nginx forwards those requests to
the `backend-py` service on port 8000. This works in both Docker Compose and
Kubernetes, where the API service is named `backend-py`.

The Go service is independent: it serves the authenticated ticket guide and
Prometheus metrics, and is not in the frontend ticket API request path.