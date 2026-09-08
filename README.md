# Inquiry Desk

An MVP three-tier inquiry management system:

- **Frontend:** React + Vite, served by Nginx
- **Backend:** ASP.NET Core 8 minimal API
- **Database:** PostgreSQL 16 with an indexed inquiry table

## Run the MVP

Install Docker Desktop or Docker Engine with Compose, then run:

```bash
docker compose up --build
```

Open `http://localhost:3000`. The API is available at `http://localhost:8080` and exposes a health check at `/health`.

## Included features

- Create and edit inquiries with validation
- Assign or unassign inquiries inline
- Change status between Open, In Progress, Resolved, and Closed
- View the inquiry list with summary counts
- Search by title, description, requester, or email
- Filter by status

The database is seeded with three sample inquiries on its first startup. To reset that data, run `docker compose down -v` before starting the stack again.
