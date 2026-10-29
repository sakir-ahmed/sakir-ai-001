# Key rotation checklist

Use after any suspected leak, when someone leaves, and every 6 months.
After changing values: `sudo bash /opt/sakir-ai/install.sh --step secrets` (or edit
the file shown) and then `sakir-ai restart`.

| Secret | Where to rotate | Where it is stored |
| --- | --- | --- |
| OpenRouter keys (hermes-core, sales, content, spare) | openrouter.ai → Keys → delete and recreate with the same limits | `data/hermes/.env`, `secrets/dt-assistant.env` |
| @SakirAI_bot token | @BotFather → `/revoke` | `data/hermes/.env`, `secrets/safe-exec.env` |
| @DTSalesDesk_bot token | @BotFather → `/revoke` | `secrets/dt-assistant.env` |
| Meta Page token | Graph API Explorer → new long-lived Page token | `secrets/dt-assistant.env` |
| Meta App Secret | App settings → Basic → Reset | `secrets/dt-assistant.env` |
| Meta verify token | generate: `openssl rand -hex 24`, update in App → Webhooks | `secrets/dt-assistant.env` |
| safe-exec token | `openssl rand -hex 24` | `secrets/safe-exec.env` and `secrets/hermes.env` (same value) |
| Internal API token | `openssl rand -hex 24` | `secrets/dt-assistant.env` and `secrets/hermes.env` (same value) |
| ai-db passwords | `ALTER ROLE sakirai PASSWORD '...'` and `hermes_ro` inside ai-db | `secrets/ai-db.env`, `DATABASE_URL` in `secrets/dt-assistant.env`, `AI_DB_RO_URL` in `secrets/hermes.env` |
| n8n DB password | `ALTER ROLE n8n PASSWORD '...'` inside n8n-db | `secrets/n8n-db.env`, `secrets/n8n.env` |
| n8n encryption key | Do NOT rotate casually: n8n credentials become unreadable. Export credentials first. | `secrets/n8n.env` |
| Grafana admin | Grafana → Profile → Change password | `secrets/grafana.env` (first start only) |
| Backup key pair | `age-keygen`; put the new public key in `/root/backup-recipient.txt`; keep the old private key until old backups expire | `/root/backup-recipient.txt` |
| SSH keys | replace `/home/sakir/.ssh/authorized_keys` | server |
