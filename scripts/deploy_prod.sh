#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${APP_IMAGE:-}" ]]; then
  echo "ERROR: APP_IMAGE is required (example: ghcr.io/<owner>/<repo>:sha-abcdef1)" >&2
  exit 2
fi

if [[ ! -f ".env" ]]; then
  echo "ERROR: .env is missing in current directory" >&2
  exit 2
fi

if [[ ! -f "config/config.yaml" ]]; then
  echo "ERROR: config/config.yaml is missing in current directory" >&2
  exit 2
fi

if [[ -n "${GHCR_USERNAME:-}" && -n "${GHCR_TOKEN:-}" ]]; then
  echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USERNAME}" --password-stdin >/dev/null
fi

export APP_IMAGE

docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --remove-orphans

echo "Waiting for /health..."
for i in {1..30}; do
  if curl -fsS "http://127.0.0.1:8000/health" >/dev/null; then
    echo "OK: service is healthy"
    exit 0
  fi
  sleep 2
done

echo "ERROR: service did not become healthy in time" >&2
docker compose -f docker-compose.prod.yml ps >&2 || true
docker compose -f docker-compose.prod.yml logs --tail=200 app >&2 || true
exit 1

