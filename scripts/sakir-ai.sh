#!/usr/bin/env bash
# =============================================================================
# sakir-ai — daily operations command (installed as /usr/local/bin/sakir-ai)
#
#   sakir-ai status              containers, health, resource use
#   sakir-ai health              full health check (same as install verify)
#   sakir-ai logs <svc> [-f]     recent logs of one service
#   sakir-ai restart [svc]       restart one service, or all
#   sakir-ai stop [svc]          stop one service, or all
#   sakir-ai start               start everything
#   sakir-ai update              backup, pull/build new images, restart
#   sakir-ai reindex             git pull knowledge + rebuild search index
#   sakir-ai backup              run the encrypted backup now
#   sakir-ai pause | resume      stop/restart automatic customer replies
#   sakir-ai secret <KEY>        print one secret value (e.g. META_VERIFY_TOKEN)
#   sakir-ai versions            image versions in use (to pin in .env)
#   sakir-ai shell <svc>         open a shell inside a container
# =============================================================================
set -Eeuo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/sakir-ai}"
# shellcheck source=../lib/common.sh
source "${INSTALL_DIR}/lib/common.sh"
# shellcheck disable=SC2034  # read by the logging helpers in lib/common.sh
LOG_FILE=/var/log/sakir-ai-ops.log

cd "$INSTALL_DIR"
[[ $EUID -eq 0 ]] || exec sudo "$0" "$@"

# Everything except one-shot jobs; Hermes included once configured.
all_services() { docker compose config --services | grep -v '^indexer$'; }

internal_api() {
  # Calls dt-assistant's internal API from inside its own container, using the
  # token already in that container's environment (never on a command line).
  local method="$1" path="$2"
  docker compose exec -T dt-assistant python -c "
import os, urllib.request
req = urllib.request.Request('http://127.0.0.1:8080${path}', method='${method}', data=b'',
      headers={'Authorization': 'Bearer ' + os.environ['INTERNAL_API_TOKEN']})
print(urllib.request.urlopen(req, timeout=10).read().decode())"
}

cmd="${1:-help}"; shift || true
case "$cmd" in
  status)
    docker compose ps --format 'table {{.Service}}\t{{.State}}\t{{.Status}}'
    echo
    # shellcheck disable=SC2046  # one argument per container id is intended
    docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}' \
      $(docker compose ps -q) 2>/dev/null || true
    ;;
  health)
    "${INSTALL_DIR}/scripts/healthcheck.sh" ;;
  logs)
    [[ $# -ge 1 ]] || die "Usage: sakir-ai logs <service> [-f]"
    svc="$1"; shift
    docker compose logs --tail 200 "$@" "$svc" ;;
  restart)
    if [[ $# -ge 1 ]]; then docker compose restart "$@"; else docker compose up -d; docker compose restart; fi ;;
  stop)
    docker compose stop "$@" ;;
  start)
    # shellcheck disable=SC2046
    docker compose up -d $(all_services) ;;
  update)
    info "Backing up before the update"
    "${INSTALL_DIR}/scripts/backup.sh"
    info "Pulling and building new images"
    docker compose pull --ignore-buildable
    docker compose build --pull
    # shellcheck disable=SC2046
    docker compose up -d --remove-orphans $(all_services)
    docker image prune -f >/dev/null
    rsync -a "${INSTALL_DIR}/hermes/skills/" "${INSTALL_DIR}/data/hermes/skills/"
    ok "Update finished"; docker compose ps ;;
  reindex)
    if git -C knowledge remote | grep -q .; then
      git -C knowledge pull --ff-only -q || warn "git pull failed; indexing local files"
    fi
    docker compose --profile jobs run --rm indexer ;;
  backup)
    "${INSTALL_DIR}/scripts/backup.sh" ;;
  pause)
    internal_api POST /internal/pause; ok "Automatic customer replies paused" ;;
  resume)
    internal_api POST /internal/resume; ok "Automatic customer replies resumed" ;;
  secret)
    [[ $# -eq 1 ]] || die "Usage: sakir-ai secret <KEY>"
    grep -h "^$1=" secrets/*.env .env 2>/dev/null | head -n1 | cut -d= -f2- || die "Not found: $1" ;;
  versions)
    docker compose images --format 'table {{.Service}}\t{{.Repository}}\t{{.Tag}}\t{{.ID}}'
    echo
    info "Pin exact tags in ${INSTALL_DIR}/.env (e.g. N8N_IMAGE=n8nio/n8n:<version>)" ;;
  shell)
    [[ $# -eq 1 ]] || die "Usage: sakir-ai shell <service>"
    docker compose exec "$1" sh -c 'command -v bash >/dev/null && exec bash || exec sh' ;;
  help|-h|--help|*)
    sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
