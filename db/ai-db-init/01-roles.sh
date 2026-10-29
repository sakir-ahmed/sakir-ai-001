#!/bin/sh
# =============================================================================
# ai-db first-start script (runs once, when the data folder is empty).
#
# Creates `hermes_ro`, a read-only role Hermes uses for briefs and /lead.
# Tables are created later by dt-assistant (schema.sql, idempotent), so the
# default privileges below make every future table readable by hermes_ro.
# =============================================================================
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'hermes_ro') THEN
    CREATE ROLE hermes_ro LOGIN PASSWORD '${HERMES_RO_PASSWORD}';
  END IF;
END
\$\$;

GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO hermes_ro;
GRANT USAGE ON SCHEMA public TO hermes_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO hermes_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE ${POSTGRES_USER} IN SCHEMA public
  GRANT SELECT ON TABLES TO hermes_ro;
SQL
