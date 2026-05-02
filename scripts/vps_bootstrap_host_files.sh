#!/usr/bin/env bash
# Одноразово кладёт на VPS то, чего нет в git и что требует deploy_prod.sh:
#   ${appDir}/.env
#   ${appDir}/config/config.yaml
#
# После этого GitHub Actions «Deploy to VPS (manual)» может только подтягивать образ
# (секреты VPS_DOTENV / VPS_CONFIG_YAML не обязательны, если файлы уже на сервере).
#
# Запуск из корня репозитория:
#   ./scripts/vps_bootstrap_host_files.sh --host VPS --user deploy --key ~/.ssh/key \
#     --env-file ./.env [--config-file ./app/config/config.yaml]

set -euo pipefail

scriptDir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repoRoot="$(cd "${scriptDir}/.." && pwd)"

host=""
port="22"
user=""
keyFile=""
appDir="/opt/simple_ai_agent_bot"
envFile=""
configFile=""

usage() {
  echo "Usage: $0 --host HOST --user USER --key PATH --env-file PATH [--config-file PATH] [--port 22] [--app-dir DIR]" >&2
  echo "  If --config-file omitted, uses app/config/config.yaml if present, else app/config/config.example.yaml" >&2
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) host="${2:-}"; shift 2 ;;
    --port) port="${2:-}"; shift 2 ;;
    --user) user="${2:-}"; shift 2 ;;
    --key) keyFile="${2:-}"; shift 2 ;;
    --app-dir) appDir="${2:-}"; shift 2 ;;
    --env-file) envFile="${2:-}"; shift 2 ;;
    --config-file) configFile="${2:-}"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1" >&2; usage ;;
  esac
done

if [[ -z "${host}" || -z "${user}" || -z "${keyFile}" || -z "${envFile}" ]]; then
  usage
fi

if [[ ! -f "${envFile}" ]]; then
  echo "ERROR: --env-file not found: ${envFile}" >&2
  exit 2
fi

if [[ ! -f "${keyFile}" ]]; then
  echo "ERROR: SSH key not found: ${keyFile}" >&2
  exit 2
fi

if [[ -z "${configFile}" ]]; then
  if [[ -f "${repoRoot}/app/config/config.yaml" ]]; then
    configFile="${repoRoot}/app/config/config.yaml"
  else
    configFile="${repoRoot}/app/config/config.example.yaml"
  fi
fi

if [[ ! -f "${configFile}" ]]; then
  echo "ERROR: config file not found: ${configFile}" >&2
  exit 2
fi

sshBase=(ssh -i "${keyFile}" -p "${port}" -o StrictHostKeyChecking=accept-new "${user}@${host}")
scpBase=(scp -i "${keyFile}" -P "${port}")

echo "==> mkdir ${appDir}/config on VPS"
"${sshBase[@]}" "mkdir -p '${appDir}/config'"

echo "==> Upload .env -> ${appDir}/.env"
"${scpBase[@]}" "${envFile}" "${user}@${host}:${appDir}/.env"
"${sshBase[@]}" "chmod 600 '${appDir}/.env'"

echo "==> Upload config (${configFile}) -> ${appDir}/config/config.yaml"
"${scpBase[@]}" "${configFile}" "${user}@${host}:${appDir}/config/config.yaml"

echo ""
echo "OK. На VPS есть .env и config/config.yaml. Дальше: vps_sync_from_repo.sh (compose + deploy script) и GitHub Actions Deploy."
