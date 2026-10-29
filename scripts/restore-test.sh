#!/usr/bin/env bash
# =============================================================================
# Sakir AI 001 — restore test (run monthly on your LAPTOP, not the server)
#
#   ./restore-test.sh sakir-ai_2026-11-01_0300.tar.age ~/keys/sakir-backup.key
#
# Needs: age, docker. It decrypts the archive into a temporary folder, loads
# ai-db.sql.gz into a throwaway Postgres container, prints row counts, lists
# the files archive, then deletes everything it created.
# A backup that has never been restored is not a backup.
# =============================================================================
set -Eeuo pipefail

ARCHIVE="${1:?Usage: restore-test.sh <archive.tar.age> <age-private-key-file>}"
KEY="${2:?Usage: restore-test.sh <archive.tar.age> <age-private-key-file>}"
command -v age >/dev/null || { echo "Install age first (https://age-encryption.org)"; exit 1; }
command -v docker >/dev/null || { echo "Install Docker first"; exit 1; }

WORK="$(mktemp -d)"
CONTAINER="sakir-restore-test-$$"
cleanup() { docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; rm -rf "$WORK"; }
trap cleanup EXIT

echo "==> Decrypting"
age -d -i "$KEY" "$ARCHIVE" | tar -xf - -C "$WORK"
ls -lh "$WORK"

echo "==> Starting a temporary Postgres"
docker run -d --name "$CONTAINER" -e POSTGRES_PASSWORD=restoretest postgres:16-alpine >/dev/null
until docker exec "$CONTAINER" pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done

echo "==> Loading ai-db dump"
gunzip -c "$WORK/ai-db.sql.gz" | docker exec -i "$CONTAINER" psql -q -U postgres >/dev/null 2>&1 || true

echo "==> Row counts in the restored ai-db"
docker exec "$CONTAINER" psql -U postgres -d sakirai -c "
  SELECT 'leads' AS table, count(*) FROM leads
  UNION ALL SELECT 'messages', count(*) FROM messages
  UNION ALL SELECT 'approvals', count(*) FROM approvals
  UNION ALL SELECT 'content_calendar', count(*) FROM content_calendar;"

echo "==> Files archive contents (top level)"
tar -tzf "$WORK/files.tgz" | cut -d/ -f1-2 | sort -u | head -n 30

echo
echo "Restore test PASSED if the counts above look right. Record it in the Task tracker."
