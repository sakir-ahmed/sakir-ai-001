#!/usr/bin/env bash
# =============================================================================
# Sakir AI 001 — health check (sakir-ai health, and the install verify step)
# Prints PASS/WARN/FAIL lines; exits 1 if anything FAILED.
# =============================================================================
set -uo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/sakir-ai}"
# shellcheck source=../lib/common.sh
source "${INSTALL_DIR}/lib/common.sh"
cd "$INSTALL_DIR" || exit 1

fails=0
pass() { printf '  %sPASS%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
wrn()  { printf '  %sWARN%s %s\n' "$C_YELLOW" "$C_RESET" "$*"; }
fail() { printf '  %sFAIL%s %s\n' "$C_RED" "$C_RESET" "$*"; fails=$((fails+1)); }

echo "Containers"
for svc in $(docker compose config --services | grep -v '^indexer$'); do
  cid="$(docker compose ps -q "$svc" 2>/dev/null)"
  if [[ -z "$cid" ]]; then
    if [[ "$svc" == "hermes" ]]; then wrn "hermes not started (run install.sh --step hermes)"; else fail "$svc not created"; fi
    continue
  fi
  state="$(docker inspect -f '{{.State.Status}}' "$cid")"
  health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid")"
  if [[ "$state" != "running" ]]; then fail "$svc is $state"
  elif [[ "$health" == "unhealthy" ]]; then fail "$svc is unhealthy"
  elif [[ "$health" == "starting" ]]; then wrn "$svc is starting"
  else pass "$svc running${health:+ ($health)}"; fi
done

echo "Endpoints"
curl -fsS --max-time 5 http://127.0.0.1:8081/health >/dev/null && pass "dt-assistant /health" || fail "dt-assistant /health"
curl -fsS --max-time 5 -o /dev/null http://127.0.0.1:5678/healthz && pass "n8n /healthz" || wrn "n8n not answering yet"
curl -fsS --max-time 5 -o /dev/null http://127.0.0.1:3000/api/health && pass "grafana" || wrn "grafana not answering yet"

domain="$(env_get .env PUBLIC_DOMAIN)"
if [[ -n "$domain" ]]; then
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "https://${domain}/meta/webhook?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=1")"
  case "$code" in
    403) pass "https://${domain}/meta/webhook reachable (rejects wrong token)" ;;
    000) wrn "https://${domain} not reachable over HTTPS yet (DNS or TLS step pending)" ;;
    *)   wrn "webhook answered HTTP $code" ;;
  esac
fi

echo "Host"
systemctl is-active --quiet nginx && pass "nginx active" || fail "nginx not active"
systemctl is-active --quiet sakir-hostops.path && pass "hostops watcher active" || fail "hostops watcher not active"
systemctl is-active --quiet sakir-backup.timer && pass "backup timer active" || wrn "backup timer not active (run --step timers)"
systemctl is-active --quiet sakir-heartbeat.timer && pass "heartbeat timer active" || wrn "heartbeat timer not active (run --step timers)"
ufw status | grep -q "Status: active" && pass "firewall active" || fail "firewall inactive"

if [[ -f /var/run/reboot-required ]]; then
  wrn "reboot pending for security updates ($(sort -u /var/run/reboot-required.pkgs 2>/dev/null | head -3 | tr '\n' ' ')) — ask Hermes to reboot in a quiet hour"
else
  pass "no reboot pending"
fi
[[ -n "$(env_get .env HC_HEARTBEAT_URL)" ]] && pass "outside heartbeat monitor configured" \
  || wrn "no outside monitor: a dead server cannot alert you (README: outside monitor)"

disk_pct="$(df --output=pcent / | tail -1 | tr -dc '0-9')"
(( disk_pct < 80 )) && pass "disk ${disk_pct}% used" || wrn "disk ${disk_pct}% used"

latest="$(find backups -maxdepth 1 -name 'sakir-ai_*.tar.age' -mmin -1500 2>/dev/null | head -n1)"
[[ -n "$latest" ]] && pass "backup from the last 25 hours: ${latest##*/}" || wrn "no backup in the last 25 hours"

missing=0
for key in TELEGRAM_OWNER_ID SALES_BOT_TOKEN OPENROUTER_API_KEY META_APP_SECRET META_PAGE_TOKEN; do
  [[ -n "$(env_get secrets/dt-assistant.env "$key")" ]] || { wrn "secret $key not set"; missing=1; }
done
(( missing == 0 )) && pass "all sales secrets set"

grep -q 'TODO' knowledge/products/dt-restora/pricing.md 2>/dev/null \
  && wrn "pricing.md still has TODOs (price questions will always go to you)" \
  || pass "pricing.md filled in"

echo
if (( fails > 0 )); then error "${fails} check(s) failed"; exit 1; fi
ok "All critical checks passed"
