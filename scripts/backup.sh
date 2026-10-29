#!/usr/bin/env bash
# =============================================================================
# Sakir AI 001 — encrypted backup (nightly at 03:00 via sakir-backup.timer)
#
# Contents of backups/<date>.tar.age:
#   ai-db.sql.gz, n8n-db.sql.gz      full Postgres dumps
#   extra/*                          dumps from scripts/backup.d/*.sh hooks
#                                    (add one per DT product database)
#   files.tgz                        compose.yml, .env, config, secrets,
#                                    Hermes state (memory, skills), knowledge,
#                                    Uptime Kuma and Grafana settings
#
# Encryption: age, with the public key in /root/backup-recipient.txt.
#             The private key is NOT on this server (Sakir keeps it).
# Off-server: copied with rclone to the remote "sakir-backup" if configured.
# Retention:  14 days locally; set lifecycle rules on the bucket for remote.
# Alerts:     any failure sends Sakir a Telegram message; optional HC_BACKUP_URL
#             (Healthchecks.io) gets start/success/fail pings, so a backup that
#             never runs (server down, timer broken) is reported too.
# =============================================================================
set -Eeuo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/sakir-ai}"
# shellcheck source=../lib/common.sh
source "${INSTALL_DIR}/lib/common.sh"
# shellcheck disable=SC2034  # read by the logging helpers in lib/common.sh
LOG_FILE=/var/log/sakir-ai-backup.log
KEEP_DAYS="${KEEP_DAYS:-14}"
RECIPIENT=/root/backup-recipient.txt

require_root

# Any failure from here on: tell Sakir, mark the run failed, exit non-zero.
on_failure() {
  local line="$1"
  error "Backup failed at line ${line}"
  hc_ping HC_BACKUP_URL /fail
  notify_telegram "BACKUP FAILED at line ${line}. Check: sudo tail -50 ${LOG_FILE}"
}
trap 'on_failure $LINENO' ERR
hc_ping HC_BACKUP_URL /start

[[ -s "$RECIPIENT" ]] || { on_failure "$LINENO (no public key at $RECIPIENT; run install.sh --step timers)"; exit 1; }

cd "$INSTALL_DIR"
DAY="$(date +%F_%H%M)"
WORK="$(mktemp -d "${INSTALL_DIR}/backups/.work.XXXX")"
trap 'rm -rf "$WORK"' EXIT

info "Backup ${DAY} started"

# ---- Databases (consistent dumps from the running containers) ----
dump_pg() {
  local svc="$1" out="$2" user
  user="$(docker compose exec -T "$svc" printenv POSTGRES_USER)"
  docker compose exec -T "$svc" pg_dumpall -U "$user" | gzip -6 > "$out"
  info "  ${svc}: $(du -h "$out" | cut -f1)"
}
dump_pg ai-db  "$WORK/ai-db.sql.gz"
dump_pg n8n-db "$WORK/n8n-db.sql.gz"

# ---- Extra hooks: one script per DT product database ----
# Each hook receives the output folder as $1, e.g. scripts/backup.d/dt-restora.sh:
#   docker exec dt-restora-db sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" \
#     --all-databases --single-transaction' | gzip > "$1/dt-restora.sql.gz"
mkdir -p "$WORK/extra"
shopt -s nullglob
for hook in "${INSTALL_DIR}"/scripts/backup.d/*.sh; do
  info "  hook: ${hook##*/}"
  bash "$hook" "$WORK/extra" || warn "  hook failed: ${hook##*/}"
done

# ---- Files (code, settings, secrets, agent memory, knowledge) ----
tar -czf "$WORK/files.tgz" \
  --exclude='data/hermes/cache' --exclude='data/hermes/logs' \
  compose.yml .env versions.env config secrets knowledge \
  data/hermes data/kuma data/grafana
info "  files: $(du -h "$WORK/files.tgz" | cut -f1)"

# ---- Encrypt into one archive ----
OUT="${INSTALL_DIR}/backups/sakir-ai_${DAY}.tar.age"
tar -cf - -C "$WORK" . | age -R "$RECIPIENT" -o "$OUT"
chmod 600 "$OUT"
ok "Encrypted archive: ${OUT} ($(du -h "$OUT" | cut -f1))"

# ---- Off-server copy ----
if rclone listremotes 2>/dev/null | grep -q '^sakir-backup:'; then
  rclone copy "$OUT" "sakir-backup:sakir-ai-backups/" --quiet
  ok "Copied off-server"
else
  warn "No rclone remote 'sakir-backup': backup is ONLY on this server."
fi

# ---- Local retention ----
find "${INSTALL_DIR}/backups" -maxdepth 1 -name 'sakir-ai_*.tar.age' -mtime +"$KEEP_DAYS" -delete
ok "Backup finished"
hc_ping HC_BACKUP_URL
