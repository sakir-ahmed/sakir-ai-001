#!/usr/bin/env bash
# =============================================================================
# Sakir AI 001 — heartbeat (every 5 minutes via sakir-heartbeat.timer)
#
# Pings the optional HC_HEARTBEAT_URL (Healthchecks.io or similar) from .env:
#   - success ping when the core is healthy (Docker up, dt-assistant healthy,
#     Hermes running, Nginx active)
#   - /fail ping with the problem in the body when something is wrong
# If the whole server dies, no ping arrives at all and the outside service
# alerts Sakir — the one failure an on-server monitor can never report.
# Does nothing when HC_HEARTBEAT_URL is not set.
# =============================================================================
set -uo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/sakir-ai}"
# shellcheck source=../lib/common.sh
source "${INSTALL_DIR}/lib/common.sh"

url="$(env_get "${INSTALL_DIR}/.env" HC_HEARTBEAT_URL)"
[[ -n "$url" ]] || exit 0

problems=()
systemctl is-active --quiet docker || problems+=("docker not active")
systemctl is-active --quiet nginx  || problems+=("nginx not active")
curl -fsS --max-time 5 -o /dev/null http://127.0.0.1:8081/health || problems+=("dt-assistant unhealthy")
if [[ "$(docker inspect -f '{{.State.Running}}' hermes 2>/dev/null)" != "true" ]]; then
  problems+=("hermes not running")
fi
disk_pct="$(df --output=pcent / | tail -1 | tr -dc '0-9')"
(( disk_pct < 90 )) || problems+=("disk ${disk_pct}% full")

if ((${#problems[@]} == 0)); then
  curl -fsS --max-time 10 --retry 3 -o /dev/null "$url" || true
else
  # The body shows up in the monitor's alert, so Sakir sees what broke.
  curl -fsS --max-time 10 --retry 3 -o /dev/null --data-raw "$(printf '%s; ' "${problems[@]}")" "${url}/fail" || true
fi
