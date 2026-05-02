#!/usr/bin/env bash
# Кладёт на VPS только секреты: ${appDir}/.env (в git не коммитится).
# config/config.yaml приезжает из репозитория при каждом деплое (GitHub Actions / vps_sync_from_repo.sh).
#
#   ./scripts/vps_bootstrap_host_files.sh --host VPS --user deploy --key ~/.ssh/key --env-file ./.env

set -euo pipefail

scriptDir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repoRoot="$(cd "${scriptDir}/.." && pwd)"

host=""
port="22"
user=""
keyFile=""
appDir="/opt/simple_ai_agent_bot"
envFile=""

usage() {
  echo "Usage: $0 --host HOST --user USER --key PATH --env-file PATH [--port 22] [--app-dir DIR]" >&2
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

sshBase=(ssh -i "${keyFile}" -p "${port}" -o StrictHostKeyChecking=accept-new "${user}@${host}")
scpBase=(scp -i "${keyFile}" -P "${port}")

echo "==> mkdir ${appDir} on VPS"
"${sshBase[@]}" "mkdir -p '${appDir}'"

echo "==> Upload .env -> ${appDir}/.env"
"${scpBase[@]}" "${envFile}" "${user}@${host}:${appDir}/.env"
"${sshBase[@]}" "chmod 600 '${appDir}/.env'"

echo ""
echo "OK. Дальше: push в git (в т.ч. app/config/config.yaml) и Deploy to VPS, или ./scripts/vps_sync_from_repo.sh"
