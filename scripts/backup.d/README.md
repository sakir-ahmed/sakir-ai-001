# Backup hooks

Each `*.sh` file here runs during the nightly backup with the output folder as
`$1`. Add one hook per DT product database when those products move to this
server. The dump is encrypted together with everything else.

Example `dt-restora.sh` (MySQL in a container named `dt-restora-db`):

```bash
#!/usr/bin/env bash
set -euo pipefail
docker exec dt-restora-db sh -c \
  'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --all-databases --single-transaction --routines' \
  | gzip -6 > "$1/dt-restora.sql.gz"
```

Example for PostgreSQL in a container named `dt-salona-db`:

```bash
#!/usr/bin/env bash
set -euo pipefail
docker exec dt-salona-db pg_dumpall -U postgres | gzip -6 > "$1/dt-salona.sql.gz"
```
