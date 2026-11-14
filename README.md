# Flame in Freefall

A web dashboard that turns NASA's microgravity combustion records (PSI repository) into ranked, comparable and cited fire-safety insight. The full design is in [the technical specification](Flame%20in%20Freefall%20—%20Technical%20Specification.md).

This site is an independent research aid. It is not endorsed by NASA and does not replace NASA flammability standards or testing.

## Run locally

Requirements: Docker with Compose.

```sh
cp .env.example .env        # then fill in the values
docker compose up -d --build
```

- Site: http://localhost:8080/
- API: http://localhost:8080/api/v1/ (interactive docs at `/api/v1/docs/`)
- Admin: http://localhost:8001/admin/ (bound to localhost only)

## Tests and linting

```sh
docker compose exec web sh -c "ruff check --no-cache . && pytest"   # back end
cd frontend && npm install && npm test && npx playwright test       # front end, against the running stack
```

## Layout

- `backend/` Django project and apps: `catalog`, `ingestion`, `ai`, `assistant`
- `frontend/` React + TypeScript app (Vite)
- `deploy/` Nginx config and image
- `docs/` decisions log and progress

See [docs/progress.md](docs/progress.md) for what is built and what is left.
