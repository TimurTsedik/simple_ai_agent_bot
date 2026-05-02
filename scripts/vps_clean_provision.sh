#!/usr/bin/env bash
# Чистая подготовка каталога приложения на VPS: остановка compose, удаление каталога,
# загрузка docker-compose + deploy_prod.sh + config из config.example.yaml, создание data/*.
#
# Запуск из корня репозитория:
#   ./scripts/vps_clean_provision.sh --host VPS --user deploy --key ~/.ssh/id_ed25519 \
#     [--port 22] [--app-dir /opt/simple_ai_agent_bot] [--env-file ./.env] \
#     [--app-image ghcr.io/owner/repo:sha-abc1234] [--ghcr-user U] [--ghcr-token T]
#
# GHCR токен на ноутбуке не обязателен: для публичного образа deploy_prod.sh делает pull без login;
# для приватного образа либо передай --ghcr-*, либо проще — запусти деплой только через GitHub Actions.
#
# Если задан --app-image, на VPS выполняется ./scripts/deploy_prod.sh (GHCR_* опциональны).

set -euo pipefail

scriptDir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repoRoot="$(cd "${scriptDir}/.." && pwd)"

usage() {
  sed -n '1,20p' "$0" | tail -n +2
  exit 2
}

host=""
port="22"
user=""
keyFile=""
appDir="/opt/simple_ai_agent_bot"
envFile=""
appImage=""
ghcrUser=""
ghcrToken=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) host="${2:-}"; shift 2 ;;
    --port) port="${2:-}"; shift 2 ;;
    --user) user="${2:-}"; shift 2 ;;
    --key) keyFile="${2:-}"; shift 2 ;;
    --app-dir) appDir="${2:-}"; shift 2 ;;
    --env-file) envFile="${2:-}"; shift 2 ;;
    --app-image) appImage="${2:-}"; shift 2 ;;
    --ghcr-user) ghcrUser="${2:-}"; shift 2 ;;
    --ghcr-token) ghcrToken="${2:-}"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1" >&2; usage ;;
  esac
done

if [[ -z "${host}" || -z "${user}" || -z "${keyFile}" ]]; then
  echo "ERROR: --host, --user, --key are required." >&2
  usage
fi

if [[ ! -f "${repoRoot}/docker-compose.prod.yml" ]]; then
  echo "ERROR: run from repo root (docker-compose.prod.yml not found near ${repoRoot})." >&2
  exit 2
fi

if [[ ! -f "${keyFile}" ]]; then
  echo "ERROR: SSH key not found: ${keyFile}" >&2
  exit 2
fi

if [[ -n "${envFile}" && ! -f "${envFile}" ]]; then
  echo "ERROR: --env-file not found: ${envFile}" >&2
  exit 2
fi

sshBase=(ssh -i "${keyFile}" -p "${port}" -o StrictHostKeyChecking=accept-new "${user}@${host}")
scpBase=(scp -i "${keyFile}" -P "${port}")

echo "==> Stopping existing stack (if any) on ${host}"
"${sshBase[@]}" "bash -s" <<EOF
set -euo pipefail
if [[ -f '${appDir}/docker-compose.prod.yml' ]]; then
  cd '${appDir}' && docker compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
fi
EOF

echo "==> Removing app directory ${appDir}"
"${sshBase[@]}" "rm -rf '${appDir}'"

echo "==> Creating directory tree"
"${sshBase[@]}" "mkdir -p '${appDir}/config' '${appDir}/scripts' \
  '${appDir}/data/logs' '${appDir}/data/runs' '${appDir}/data/memory/sessions' \
  '${appDir}/data/users' '${appDir}/data/skills' '${appDir}/data/scheduler' \
  '${appDir}/data/models' '${appDir}/backups'"

echo "==> Uploading compose + deploy script + fresh config (from config.example.yaml)"
"${scpBase[@]}" "${repoRoot}/docker-compose.prod.yml" "${user}@${host}:${appDir}/docker-compose.prod.yml"
"${scpBase[@]}" "${repoRoot}/scripts/deploy_prod.sh" "${user}@${host}:${appDir}/scripts/deploy_prod.sh"
"${scpBase[@]}" "${repoRoot}/app/config/config.example.yaml" "${user}@${host}:${appDir}/config/config.yaml"

"${sshBase[@]}" "chmod +x '${appDir}/scripts/deploy_prod.sh'"

if [[ -n "${envFile}" ]]; then
  echo "==> Uploading .env"
  "${scpBase[@]}" "${envFile}" "${user}@${host}:${appDir}/.env"
fi

echo ""
echo "Done. Next steps:"
echo "  1) Ensure '${appDir}/.env' on the server (--env-file or scp .env)."
echo "  2) Deploy image: GitHub Actions 'Deploy to VPS (manual)' (без токена на Mac), или:"
if [[ -n "${appImage}" ]]; then
  echo "==> Running deploy with APP_IMAGE=${appImage} (GHCR login only if both --ghcr-user and --ghcr-token set)"
  "${sshBase[@]}" "cd '${appDir}' && APP_IMAGE='${appImage}' GHCR_USERNAME='${ghcrUser:-}' GHCR_TOKEN='${ghcrToken:-}' ./scripts/deploy_prod.sh"
else
  echo "     ssh ... \"cd ${appDir} && APP_IMAGE=ghcr.io/<owner>/<repo>:sha-<tag> ./scripts/deploy_prod.sh\""
  echo "     (для публичного образа GHCR_USERNAME/GHCR_TOKEN не нужны)"
fi
echo "  3) Tenant data: при необходимости восстанови data/memory/sessions/... из бэкапа."
