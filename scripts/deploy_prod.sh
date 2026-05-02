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

if [[ -n "${GHCR_USERNAME:-}" && -n "${GHCR_TOKEN:-}" ]]; then
  echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USERNAME}" --password-stdin >/dev/null
fi

# Resolving config/config.yaml (mount expects a host file). Primary path: workflow scps it from app/config/config.yaml.
# Fallbacks: (1) public raw from GitHub when CONFIG_SOURCE_* set (2) file baked into APP_IMAGE at /app/app/config/config.yaml.
if [[ ! -f "config/config.yaml" ]]; then
  mkdir -p config
  configSourceRepo="${CONFIG_SOURCE_REPO:-}"
  configSourceRef="${CONFIG_SOURCE_REF:-}"
  if [[ -n "${configSourceRepo}" && -n "${configSourceRef}" ]]; then
    fetchUrl="https://raw.githubusercontent.com/${configSourceRepo}/${configSourceRef}/app/config/config.yaml"
    echo "config/config.yaml not found locally; trying: ${fetchUrl}"
    if curl -fsSL -o "config/config.yaml" "${fetchUrl}"; then
      echo "Fetched config/config.yaml from GitHub (public raw)."
    else
      echo "Raw fetch failed (private repo or bad ref); will try extracting from image." >&2
    fi
  fi
fi

if [[ ! -f "config/config.yaml" ]]; then
  echo "config/config.yaml still missing; extracting from image ${APP_IMAGE} (same tree as the built image)."
  tmpFile="$(mktemp)"
  if docker run --rm --entrypoint cat "${APP_IMAGE}" /app/app/config/config.yaml > "${tmpFile}" 2>/dev/null && [[ -s "${tmpFile}" ]]; then
    mv -f "${tmpFile}" config/config.yaml
    echo "Wrote config/config.yaml from container filesystem."
  else
    rm -f "${tmpFile}"
    echo "Could not read /app/app/config/config.yaml from ${APP_IMAGE} (login/pull issue or image layout changed)." >&2
  fi
fi

if [[ ! -f "config/config.yaml" ]]; then
  echo "ERROR: config/config.yaml is missing in current directory" >&2
  echo "Hint: In Actions → Run workflow, set 'Use workflow from' to the branch with the latest deploy workflow (usually main). The ref input only selects checkout; the workflow YAML comes from the branch you pick in the UI." >&2
  exit 2
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

