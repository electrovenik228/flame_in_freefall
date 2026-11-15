# Flame in Freefall

A web dashboard that turns NASA's microgravity combustion records (the PSI repository) into ranked, comparable and cited fire-safety insight. The full design is in [the technical specification](Flame%20in%20Freefall%20—%20Technical%20Specification.md).

This site is an independent research aid. It is not endorsed by NASA and does not replace NASA flammability standards or testing.

## Run locally

Requirements: Docker with Compose. Nothing else is needed on the host.

```sh
git clone <repository> flame_in_freefall && cd flame_in_freefall
cp .env.example .env      # set DJANGO_SECRET_KEY and POSTGRES_PASSWORD (both in DATABASE_URL too)
docker compose up -d --build
docker compose exec web python manage.py load_seed          # 23 PSI records, 749 test runs, environments
docker compose exec web python manage.py import_ai_output   # stored AI summaries and attributes, no Claude request
```

- Site: http://localhost:8080/
- API: http://localhost:8080/api/v1/ (interactive docs at `/api/v1/docs/`)
- Admin: `docker compose exec web python manage.py createsuperuser`, then http://localhost:8001/admin/

The site works without a Claude API key: everything except the assistant reads stored data. To use the assistant or regenerate AI output, set `ANTHROPIC_API_KEY` to a key with credit.

If port 8080 or 8001 is taken: `HTTP_PORT=8090 ADMIN_PORT=8002 docker compose up -d`.

## Regenerate AI output

```sh
docker compose exec web python manage.py generate_ai              # extraction, summaries, judgments; unchanged input is skipped
docker compose exec web python manage.py generate_ai --report     # the step 6 check only, no API call
docker compose exec web python manage.py export_ai_output         # write backend/fixtures/ai_output.json for others
```

## Tests and linting

```sh
docker compose exec web sh -c "ruff check --no-cache . && pytest"   # back end, 66 tests
cd frontend && npm install && npx playwright install chromium
npm test && npx eslint src && npx tsc --noEmit                       # front end unit tests and types
npx playwright test                                                  # browser tests against the running stack
E2E_ASSISTANT=live npx playwright test e2e/assistant.spec.ts         # the five demo questions; needs API credit
```

## Deploy

One server reached by IP address over SSH. Set up the server once with [deploy/server-setup.md](deploy/server-setup.md), set `DJANGO_DEBUG=False` and the server address in `.env`, then:

```sh
deploy/deploy.sh user@server
```

The admin is never exposed publicly: `ssh -L 8001:localhost:8001 user@server`, then http://localhost:8001/admin/.

## Layout

- `backend/` Django project and apps: `catalog` (records, API, ranking), `ingestion` (PSI parsers and loader), `ai` (Claude jobs and checks), `assistant` (streaming chat)
- `backend/fixtures/` the PSI seed set and the stored AI output
- `frontend/` React + TypeScript app (Vite)
- `deploy/` Nginx config and image, deploy and backup scripts
- `docs/` [progress](docs/progress.md), [decisions](docs/decisions.md), [demo script](docs/demo-script.md), [known limitations](docs/limitations.md)
