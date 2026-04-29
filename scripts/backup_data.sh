#!/usr/bin/env bash
set -euo pipefail

baseDir="${BASE_DIR:-/opt/simple_ai_agent_bot}"
srcDir="${SRC_DIR:-${baseDir}/data}"
dstDir="${DST_DIR:-${baseDir}/backups}"
retentionDays="${RETENTION_DAYS:-14}"

ts="$(date -u +%Y%m%d_%H%M%S)"
outFile="${dstDir}/data_${ts}.tar.gz"

if [[ -d "${srcDir}" ]]; then
  :
else
  echo "ERROR: srcDir does not exist: ${srcDir}" >&2
  exit 2
fi

mkdir -p "${dstDir}"

tar -C "${srcDir}" -czf "${outFile}" .
find "${dstDir}" -type f -name "data_*.tar.gz" -mtime +"${retentionDays}" -delete

echo "Backup written: ${outFile}"

