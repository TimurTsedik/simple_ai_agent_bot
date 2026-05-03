#!/usr/bin/env bash
# Один раз залить на VPS локальные каталоги (как в docker-compose: ./data → /app/data):
#   data/scheduler  data/memory  data/users  data/state
# Остальное под data/ (runs, logs, …) не трогает.
#
# Запуск из корня репозитория (где лежит каталог data/):
#   ./scripts/vps_upload_data_seed.sh --host 1.2.3.4 --user deploy --key ~/.ssh/mykey [--port 22] [--app-dir /opt/...]
#   ./scripts/vps_upload_data_seed.sh ... --dry-run   # пробел перед --dry-run; chmod 600 на приватный ключ
# --key: только приватный ключ (файл без .pub), не публичный .pub
#
# Повторный запуск: rsync допишет/обновит файлы; без флага --delete ничего на сервере не удаляет.

set -euo pipefail

scriptDir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repoRoot="$(cd "${scriptDir}/.." && pwd)"

host=""
port="22"
user=""
keyFile=""
appDir="/opt/simple_ai_agent_bot"
dryRun=""
deleteFlag=""

usage() {
  echo "Usage: $0 --host HOST --user USER --key PATH [--port 22] [--app-dir DIR] [--dry-run] [--delete]" >&2
  echo "  --dry-run  только показать, что будет передано" >&2
  echo "  --delete   у rsync: зеркалировать (удалить на сервере лишнее внутри этих четырёх каталогов)" >&2
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) host="${2:-}"; shift 2 ;;
    --port) port="${2:-}"; shift 2 ;;
    --user) user="${2:-}"; shift 2 ;;
    --key) keyFile="${2:-}"; shift 2 ;;
    --app-dir) appDir="${2:-}"; shift 2 ;;
    --dry-run) dryRun="1"; shift 1 ;;
    --delete) deleteFlag="1"; shift 1 ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1" >&2; usage ;;
  esac
done

if [[ -z "${host}" || -z "${user}" || -z "${keyFile}" ]]; then
  usage
fi

if [[ ! -d "${repoRoot}/data" ]]; then
  echo "ERROR: no ${repoRoot}/data — run from repository root." >&2
  exit 2
fi

if [[ ! -f "${keyFile}" ]]; then
  echo "ERROR: SSH key not found: ${keyFile}" >&2
  exit 2
fi

if [[ "${keyFile}" == *.pub ]]; then
  echo "ERROR: --key must be the private key (path without .pub). You passed a public key: ${keyFile}" >&2
  exit 2
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "ERROR: rsync not found (install with package manager)." >&2
  exit 2
fi

qKey="$(printf '%q' "${keyFile}")"
rsyncRsh="ssh -i ${qKey} -p ${port} -o StrictHostKeyChecking=accept-new"
remoteBase="${user}@${host}:${appDir}"

echo "==> mkdir ${appDir}/data/... on VPS"
ssh -i "${keyFile}" -p "${port}" -o StrictHostKeyChecking=accept-new "${user}@${host}" \
  "mkdir -p '${appDir}/data/scheduler' '${appDir}/data/memory' '${appDir}/data/users' '${appDir}/data/state'"

subdirs=(scheduler memory users state)
rsyncArgs=(-a -z)
if [[ -n "${dryRun}" ]]; then
  rsyncArgs+=(-n -v)
fi
if [[ -n "${deleteFlag}" ]]; then
  rsyncArgs+=(--delete)
fi

for name in "${subdirs[@]}"; do
  src="${repoRoot}/data/${name}"
  if [[ ! -d "${src}" ]]; then
    echo "WARN: skip missing local dir: ${src}"
    continue
  fi
  echo "==> rsync data/${name}/ -> ${appDir}/data/${name}/"
  rsync "${rsyncArgs[@]}" -e "${rsyncRsh}" "${src}/" "${remoteBase}/data/${name}/"
done

echo ""
echo "OK. На сервере: ${appDir}/data/{scheduler,memory,users,state}. Перезапуск контейнера при необходимости: docker compose -f docker-compose.prod.yml up -d"
