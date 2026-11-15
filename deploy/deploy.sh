#!/usr/bin/env bash
# Deploy over SSH (section 12). Usage: deploy/deploy.sh user@server [remote path]
# Needs: SSH access, Docker with Compose on the server, and a local .env for production.
# It copies the repository and .env, builds, starts, loads data and checks health.
# It never deletes the database volume or the backups.
set -euo pipefail

TARGET="${1:?usage: deploy/deploy.sh user@server [remote path]}"
REMOTE_DIR="${2:-flame_in_freefall}"
HOST="${TARGET#*@}"
cd "$(dirname "$0")/.."

[ -f .env ] || { echo "No .env here. Copy .env.example and fill it in." >&2; exit 1; }
grep -q "^DJANGO_ALLOWED_HOSTS=.*${HOST}" .env || { echo "DJANGO_ALLOWED_HOSTS in .env does not include ${HOST}." >&2; exit 1; }
grep -q '^DJANGO_DEBUG=False' .env || { echo "Set DJANGO_DEBUG=False in .env before deploying." >&2; exit 1; }

COMPOSE="docker compose -f docker-compose.prod.yml"

echo "Copying the repository to ${TARGET}:${REMOTE_DIR}"
ssh "${TARGET}" "mkdir -p ${REMOTE_DIR}/backups"
git ls-files -z | rsync -az --from0 --files-from=- ./ "${TARGET}:${REMOTE_DIR}/"
rsync -az --chmod=F600 .env "${TARGET}:${REMOTE_DIR}/.env"

echo "Building and starting"
ssh "${TARGET}" "cd ${REMOTE_DIR} && ${COMPOSE} up -d --build --remove-orphans"

echo "Loading PSI records and stored AI output (safe to repeat)"
ssh "${TARGET}" "cd ${REMOTE_DIR} && ${COMPOSE} exec -T web sh -c 'python manage.py load_seed && python manage.py import_ai_output'"

echo "Checking health"
for _ in $(seq 1 20); do
  if curl -fsS "http://${HOST}/api/v1/health/" >/dev/null; then
    echo "Site:   http://${HOST}/"
    echo "Health: http://${HOST}/api/v1/health/"
    echo "Admin:  ssh -L 8001:localhost:8001 ${TARGET}, then http://localhost:8001/admin/"
    exit 0
  fi
  sleep 3
done
echo "The health endpoint did not answer on http://${HOST}/." >&2
exit 1
