#!/usr/bin/env bash
# Выполнять на VPS под root, если каталоги под appDir были созданы от root
# (deploy тогда не может писать config/config.yaml — см. deploy_prod.sh / scp в Actions).
#
#   sudo bash scripts/vps_fix_app_dir_ownership.sh
#   sudo bash scripts/vps_fix_app_dir_ownership.sh /opt/simple_ai_agent_bot deploy

set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "ERROR: run as root (sudo)." >&2
  exit 2
fi

appDir="${1:-/opt/simple_ai_agent_bot}"
owner="${2:-deploy}"
group="${3:-${owner}}"

echo "==> appDir=${appDir} owner=${owner}:${group}"

rm -rf "${appDir}/config"
mkdir -p "${appDir}/config" "${appDir}/data" "${appDir}/scripts"
chown -R "${owner}:${group}" "${appDir}"
chmod u+rwX,g+rX,o+rX "${appDir}/config" "${appDir}/data" "${appDir}/scripts" 2>/dev/null || true

echo "OK. Перезапусти деплой в GitHub Actions (или scp config вручную)."
