#!/usr/bin/env bash
# Обновить на VPS только то, что в git: compose, deploy_prod.sh, свежий config.example → config/config.yaml.
# Удалить на сервере устаревшие файлы config/tools.yaml и config/schedules.yaml (раньше использовались bind-mount’ами).
# Каталог data/ и .env не трогает.
#
# Деплой образа после этого:
#   • проще всего — GitHub Actions «Deploy to VPS (manual)» (токен GHCR не нужен на твоём Mac);
#   • или по SSH, если образ публичный: токен тоже не нужен:
#       ssh ... "cd /opt/simple_ai_agent_bot && APP_IMAGE=ghcr.io/owner/repo:sha-xxx ./scripts/deploy_prod.sh"
#
# Запуск из корня репозитория:
#   ./scripts/vps_sync_from_repo.sh --host VPS --user deploy --key ~/.ssh/key [--port 22] [--app-dir DIR] [--skip-config]
#   --skip-config — не заливать config/config.yaml (если уже положил вручную / vps_bootstrap_host_files.sh)

set -euo pipefail

scriptDir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repoRoot="$(cd "${scriptDir}/.." && pwd)"

host=""
port="22"
user=""
keyFile=""
appDir="/opt/simple_ai_agent_bot"
skipConfig="0"

usage() {
  echo "Usage: $0 --host HOST --user USER --key PATH [--port 22] [--app-dir DIR] [--skip-config]" >&2
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) host="${2:-}"; shift 2 ;;
    --port) port="${2:-}"; shift 2 ;;
    --user) user="${2:-}"; shift 2 ;;
    --key) keyFile="${2:-}"; shift 2 ;;
    --app-dir) appDir="${2:-}"; shift 2 ;;
    --skip-config) skipConfig="1"; shift 1 ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1" >&2; usage ;;
  esac
done

if [[ -z "${host}" || -z "${user}" || -z "${keyFile}" ]]; then
  usage
fi

if [[ ! -f "${repoRoot}/docker-compose.prod.yml" ]]; then
  echo "ERROR: run from repository root." >&2
  exit 2
fi

if [[ ! -f "${keyFile}" ]]; then
  echo "ERROR: SSH key not found: ${keyFile}" >&2
  exit 2
fi

sshBase=(ssh -i "${keyFile}" -p "${port}" -o StrictHostKeyChecking=accept-new "${user}@${host}")
scpBase=(scp -i "${keyFile}" -P "${port}")

echo "==> Ensuring directories exist: config/, scripts/"
"${sshBase[@]}" "mkdir -p '${appDir}/config' '${appDir}/scripts'"

echo "==> Removing legacy paths (file or mistaken directory): config/tools.yaml, config/schedules.yaml"
"${sshBase[@]}" "rm -rf '${appDir}/config/tools.yaml' '${appDir}/config/schedules.yaml' 2>/dev/null || true"

echo "==> Uploading docker-compose.prod.yml, deploy_prod.sh"
"${scpBase[@]}" "${repoRoot}/docker-compose.prod.yml" "${user}@${host}:${appDir}/docker-compose.prod.yml"
"${scpBase[@]}" "${repoRoot}/scripts/deploy_prod.sh" "${user}@${host}:${appDir}/scripts/deploy_prod.sh"
if [[ "${skipConfig}" == "1" ]]; then
  echo "==> Skipping config/config.yaml (--skip-config)"
else
  echo "==> Uploading config/config.yaml (from config.example.yaml)"
  "${scpBase[@]}" "${repoRoot}/app/config/config.example.yaml" "${user}@${host}:${appDir}/config/config.yaml"
fi

"${sshBase[@]}" "chmod +x '${appDir}/scripts/deploy_prod.sh'"

echo ""
echo "Done. Дальше:"
echo "  1) Запусти деплой образа через GitHub Actions (секреты уже в GitHub) — токен на ноутбуке не нужен."
echo "  2) Или по SSH (публичный образ GHCR — без docker login):"
echo "       ssh -i ${keyFile} -p ${port} ${user}@${host} \\"
echo "         \"cd '${appDir}' && APP_IMAGE=ghcr.io/<owner>/<repo>:sha-<tag> ./scripts/deploy_prod.sh\""
