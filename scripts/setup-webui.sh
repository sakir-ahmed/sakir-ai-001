#!/usr/bin/env bash
# Install the optional loopback-only UI, preserving production containers.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
docker compose version >/dev/null
curl --fail --silent --show-error http://127.0.0.1:11434/api/tags >/dev/null
if docker container inspect sakir_ai_001_webui >/dev/null 2>&1; then
  echo 'Existing UI found; refusing automatic recreation. Review and approve an update.' >&2
  exit 1
fi
if ss -H -ltn 'sport = :8082' | read -r _; then
  echo 'Port 8082 is occupied; no changes made.' >&2
  exit 1
fi
sakir-ai backup
install -d -m 700 /opt/sakir-ai/data/webui
install -m 644 "$source_dir/compose.webui.yml" /opt/sakir-ai/compose.webui.yml
docker compose -p sakir-ai-webui -f /opt/sakir-ai/compose.webui.yml up -d
echo 'Private UI installed on 127.0.0.1:8082; wait for /health before onboarding.'
echo 'Create the owner account over a private SSH tunnel before any public proxy is enabled.'
