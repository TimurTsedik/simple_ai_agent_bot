#!/usr/bin/env bash
set -euo pipefail

showUsage() {
  cat <<'EOF'
Usage:
  scripts/fetch_server_snapshot.sh \
    --host <ip-or-host> \
    --user <ssh-user> \
    --key <path-to-ssh-private-key> \
    [--port <ssh-port>] \
    [--remote-app-dir <path>] \
    [--local-project-root <path>]

Example:
  scripts/fetch_server_snapshot.sh \
    --host 187.124.165.192 \
    --user deploy \
    --key ~/.ssh/simple_ai_agent_bot_vps_deploy \
    --port 22 \
    --remote-app-dir /opt/simple_ai_agent_bot \
    --local-project-root .
EOF
}

host=""
user=""
keyPath=""
port="22"
remoteAppDir="/opt/simple_ai_agent_bot"
localProjectRoot="."

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      host="${2:-}"
      shift 2
      ;;
    --user)
      user="${2:-}"
      shift 2
      ;;
    --key)
      keyPath="${2:-}"
      shift 2
      ;;
    --port)
      port="${2:-}"
      shift 2
      ;;
    --remote-app-dir)
      remoteAppDir="${2:-}"
      shift 2
      ;;
    --local-project-root)
      localProjectRoot="${2:-}"
      shift 2
      ;;
    -h|--help)
      showUsage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      showUsage
      exit 2
      ;;
  esac
done

if [[ -z "${host}" || -z "${user}" || -z "${keyPath}" ]]; then
  echo "ERROR: --host, --user, --key are required." >&2
  showUsage
  exit 2
fi

if [[ -f "${keyPath}" ]]; then
  :
else
  echo "ERROR: key file is not found: ${keyPath}" >&2
  exit 2
fi

timestampUtc="$(date -u +%Y%m%d_%H%M%S)"
snapshotTag="server_${host}_${timestampUtc}"
projectRootResolved="$(cd "${localProjectRoot}" && pwd)"

localConfigDir="${projectRootResolved}/app/config/server_snapshots/${snapshotTag}"
localLogsDir="${projectRootResolved}/data/logs/server_snapshots/${snapshotTag}"
localRunsDir="${projectRootResolved}/data/runs/server_snapshots/${snapshotTag}"
localSchedulerDir="${projectRootResolved}/data/scheduler/server_snapshots/${snapshotTag}"
localMetaDir="${projectRootResolved}/data/server_snapshots_meta/${snapshotTag}"

mkdir -p "${localConfigDir}"
mkdir -p "${localLogsDir}"
mkdir -p "${localRunsDir}"
mkdir -p "${localSchedulerDir}"
mkdir -p "${localMetaDir}"

sshBase=(ssh -i "${keyPath}" -p "${port}")
scpBase=(scp -i "${keyPath}" -P "${port}")
remote="${user}@${host}"

echo "Collecting snapshot from ${remote}:${remoteAppDir}"

# 1) Server-side meta
"${sshBase[@]}" "${remote}" "uname -a; date -u; date; pwd" > "${localMetaDir}/server_info.txt"
"${sshBase[@]}" "${remote}" "ls -la \"${remoteAppDir}\"" > "${localMetaDir}/app_dir_listing.txt"

# 2) Config files (+ tenant tools/schedules under admin Telegram id)
"${scpBase[@]}" "${remote}:${remoteAppDir}/config/config.yaml" "${localConfigDir}/config.yaml" || true
adminTelegramUserId="${ADMIN_TELEGRAM_USER_ID:-16739703}"
tenantSessionsPath="${remoteAppDir}/data/memory/sessions/telegramUser_${adminTelegramUserId}"
"${scpBase[@]}" "${remote}:${tenantSessionsPath}/tools.yaml" "${localConfigDir}/tools.yaml" || true
"${scpBase[@]}" "${remote}:${tenantSessionsPath}/schedules.yaml" "${localConfigDir}/schedules.yaml" || true

# 3) Scheduler state
"${scpBase[@]}" "${remote}:${remoteAppDir}/data/scheduler/jobs_state.json" "${localSchedulerDir}/jobs_state.json" || true

# 4) Logs and runs
"${scpBase[@]}" -r "${remote}:${remoteAppDir}/data/logs/." "${localLogsDir}/" || true
"${scpBase[@]}" -r "${remote}:${remoteAppDir}/data/runs/." "${localRunsDir}/" || true

# 5) Quick reminder diagnostics (best-effort)
python3 - "${localLogsDir}" "${localMetaDir}" <<'PY'
import json
import pathlib
import sys

logs_dir = pathlib.Path(sys.argv[1])
meta_dir = pathlib.Path(sys.argv[2])
summary_path = meta_dir / "reminder_events_summary.txt"

events = []
if logs_dir.exists():
    for one_file in sorted(logs_dir.glob("*.jsonl")):
        try:
            for line in one_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event_type = str(obj.get("eventType", ""))
                if "reminder" in event_type or "schedule_reminder" in line:
                    events.append((one_file.name, obj))
        except OSError:
            pass

with summary_path.open("w", encoding="utf-8") as out_file:
    out_file.write(f"Found reminder-related events: {len(events)}\n")
    out_file.write("-" * 80 + "\n")
    for file_name, obj in events[-200:]:
        out_file.write(f"{file_name} :: {json.dumps(obj, ensure_ascii=False)}\n")
PY

echo "Snapshot ready (placed into project folders):"
echo "  config:    ${localConfigDir}"
echo "  logs:      ${localLogsDir}"
echo "  runs:      ${localRunsDir}"
echo "  scheduler: ${localSchedulerDir}"
echo "  meta:      ${localMetaDir}"
echo "Main files:"
echo "  ${localConfigDir}/schedules.yaml"
echo "  ${localSchedulerDir}/jobs_state.json"
echo "  ${localMetaDir}/reminder_events_summary.txt"

