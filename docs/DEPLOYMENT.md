# Deploying Sakir AI 001 from Git

This guide maps reusable core code to installed files, explains what belongs in
Git, and gives the checklist for a second server. Git is the source of code;
secrets and runtime state have their own provisioning and recovery process.

## Source inventory

| Capability / installed entry point | Committed source | Provisioning |
| --- | --- | --- |
| Installation steps and host prerequisites | `install.sh`, `lib/common.sh` | `sudo bash install.sh` on fresh supported Ubuntu |
| `/usr/local/bin/sakir-ai` | `scripts/sakir-ai.sh` | `layout` creates symlink |
| Container definitions and image defaults | `compose.yml`, `versions.env`, `services/*/Dockerfile`, requirements files | `layout`, `stack`, `hermes` |
| Server action runner `/usr/local/bin/sakir-hostops` | `hostops/sakir-hostops`, `config/allowlist.yaml` | `hostops` |
| Backup, heartbeat, health and reindex commands | `scripts/backup.sh`, `scripts/heartbeat.sh`, `scripts/healthcheck.sh`, `services/indexer/` | command wrapper / service units |
| `/etc/systemd/system/sakir-*` | `systemd/` (eight units) | `hostops`, `timers` |
| `/etc/logrotate.d/sakir-ai` | `config/logrotate-sakir-ai` | `timers` |
| Nginx public proxy and rate limits | `config/nginx/*.template`, `config/nginx/sakir-ai-ratelimit.conf` | `nginx` substitutes domain/install path; `tls` adds certificate configuration |
| Private Tailscale serving rules | `step_tailscale` in `install.sh` | optional `tailscale` step |
| Sales, approvals, policy and schema | `services/dt-assistant/`, `config/dt-assistant.yaml`, `db/ai-db-init/` | `stack` |
| Speech, safe actions and settings dashboard | `services/stt/`, `tts/`, `safe-exec/`, `settings-ui/` | `stack`; provider settings provisioned separately |
| Agent tool commands and role instructions | `tools/sakir.py`, `hermes/skills/` | `layout`, `hermes` |
| Initial business/personal knowledge | `knowledge-templates/` | `knowledge`; owner fills live copy |
| Optional coding-tool installers | `scripts/install-ai-tools.sh` | optional `aitools` step; owner signs in |
| Deployment drift report | `scripts/audit-deployment.py` | read-only; Python standard library + Git |

The installer is the versioned command recipe, not a terminal-history transcript.
When a one-off command fixes something needed on future servers, move that behavior
into its installer step or a script and add validation. Do not depend on shell
history, chat instructions or uncommitted patches to recreate the service.

## What stays outside Git

Never commit `.env`, `secrets/`, rclone credentials, TLS private keys, backup private
keys, database dumps, runtime `data/`, customer records or complete terminal logs.
Live knowledge is separate from the seed templates and may contain private facts.
The owner provisions credentials interactively and retains the backup private key
in the password manager, not on the server. Commit variable names/placeholders and
generation logic, never actual credential values.

Generated host configuration is recreated from templates/installer settings.
Do not copy another server's hostname, SSH identity, firewall state, Tailscale
identity, public IP or certificate files into a universal deployment template.
Unrelated production sites and migration configurations are outside this bundle.

## Fresh-server checklist

- [ ] Select Ubuntu 22.04/24.04, supported architecture, minimum 8 GB RAM and 40 GB
  available disk (16+ GB RAM recommended). Review actual CPU/RAM caps and workload.
- [ ] Choose a new hostname, public domain, admin account and DNS record. Preserve
  console access and a working SSH key before applying installer security steps.
- [ ] Select a reviewed branch/tag/commit containing the required fixes. Until PR
  changes merge, use their branch explicitly; do not assume main includes them.
- [ ] Clone as the admin user and check out the exact reviewed revision:

  ```bash
  git clone https://github.com/sakir-ahmed/sakir-ai-001.git ~/sakir-ai-001
  cd ~/sakir-ai-001
  git fetch origin
  git checkout <reviewed-tag-or-commit>
  git rev-parse HEAD
  ```

- [ ] Read AGENTS.md, ARCHITECTURE.md, DECISIONS.md and OPERATIONS.md. Installer
  execution provisions the host, firewall, users and services; review before running.
- [ ] Install interactively, overriding only non-secret host parameters as needed:

  ```bash
  sudo env ADMIN_USER=sakir SERVER_HOSTNAME=sakir-ai-002 TIMEZONE=Asia/Dhaka bash install.sh
  ```

- [ ] Enter the destination domain/account credentials when prompted. Use separate
  Telegram bots or deliberately migrate the existing gateway: two active servers
  must not compete to poll the same bot token or send duplicate customer replies.
- [ ] Save the newly generated backup private key privately. Off-site storage is
  deferred by Sakir as of 2026-10-31; a local archive does not survive server loss.
- [ ] Resolve DNS/TLS, fill approved knowledge, reindex, configure schedules and
  verify all provider permissions. Installed containers do not imply these are done.
- [ ] Run `sakir-ai health`; resolve FAIL results and record warnings. Test customer
  approval flow, speech, alert delivery and backup/restore using isolated data.
- [ ] Record source revision, image tags/digests and outcome in the deployment record.

`versions.env` currently contains moving `latest`/major tags. This supports repeatable
setup steps, not byte-identical future images. Pin reviewed image tags/digests in
versioned defaults when validated; retain per-server overrides privately. Package
repositories and optional CLI installers also move, so a clean second-server test
remains an acceptance gate rather than an assumed guarantee.

## Existing-server changes

Before an upgrade, use [OPERATIONS.md](OPERATIONS.md) and take a verified backup.
Run the read-only audit first. `install.sh --step layout` copies source using rsync
with deletion and copies default configs; review/preserve intentional live config
changes before using it. Avoid running the full installer on an established server
merely to refresh one script. A targeted deployment must record source revision,
file checksum, retained rollback copy and verification outcome.

Audit against a selected commit (exit 0 = matched core; 1 = drift/missing/extra):

```bash
sudo python3 scripts/audit-deployment.py \
  --source "$PWD" --revision <reviewed-tag-or-commit> --installed /opt/sakir-ai
```

The audit prints paths and status, never contents. It checks core file contents;
it does not certify ownership/modes, generated Nginx/TLS configuration, provider
accounts, installed OS packages or successful business workflows. Symlinked core
files are flagged rather than followed. Excluded rollback/candidate files are
operational artifacts, not active source to import into Git.

## Live source audit — 2026-10-31

Compared `/opt/sakir-ai` against revision `173492c` through Termius:

- 68 core files matched exactly; no extra core files found in audited directories.
- `compose.yml` and `scripts/sakir-ai.sh` matched committed historical revision
  `b06c9ce3e794` exactly. `install.sh` matched `f272cd5b8746` exactly. These are
  deployment lag, not uncommitted live-only fixes.
- Backup script matched the committed recovery fix (SHA-256
  `4afd60e8ccf377404beddceceefdc00d33e6e32a06de98a2a376bb93b143c957`).
- Four files were not deployed: this audit script and the three settings-ui files.
- All eight installed Sakir systemd units, the hostops runner and logrotate file
  matched their bundle sources. The `sakir-ai` entry point is a symlink.
- Nginx also contains unrelated migration/product sites; those were inventoried
  by filename only and are not claimed as captured by this AI-stack audit.

No missing live-only core script was discovered in this scope. Full OS/provisioner
state and a clean deployment on another server have not been verified.

## Dedicated Cloudflare-proxied hostname

Owner-selected hostname: `ai001.sakir.bd` (2026-10-31). Its A record stays proxied.
With a pre-existing certbot ACME account and the installed bundle:

```bash
sudo bash /opt/sakir-ai/scripts/setup-public-domain.sh ai001.sakir.bd
```

The command backs up first, renders a dedicated site from the committed template,
validates/reloads Nginx, issues/reuses a Let's Encrypt certificate, verifies origin
TLS and public invalid-token rejection, then updates PUBLIC_DOMAIN and the saved sales PUBLIC_BASE_URL. It preserves
unrelated sites. Cloudflare must pass HTTP-01 validation to the origin; certificate
errors must be fixed rather than bypassed. It does not change Cloudflare settings,
external Meta subscriptions or existing container environments.

Public root and unknown paths return 404 by design. The webhook uses `/meta/webhook`;
there is no public generic `/api/v1` or admin dashboard. New public APIs require a
specific contract and authentication review. Existing HTTPS sites are reused on
subsequent runs; inspect unexpected pre-existing site files before running.

### Activate saved domain in existing containers

After explicit owner approval for container recreation, and after a current backup:

```bash
cd /opt/sakir-ai
sudo docker compose up -d --no-deps dt-assistant n8n
curl -fsS http://127.0.0.1:8081/health
curl -fsS http://127.0.0.1:5678/healthz
sakir-ai health
```

Completed with Sakir's explicit approval on 2026-10-31 at approximately 02:57 Dhaka.
Persistent volumes were retained. Verified active `PUBLIC_BASE_URL` for sales and
`N8N_HOST` / `WEBHOOK_URL` for n8n against the new hostname without printing secrets.
Sales and n8n health endpoints passed. Overall health still fails on the existing
STT issue; pricing knowledge still contains TODOs. This command refreshes selected
container configuration, not source code or images, and does not prove a business
workflow has completed.
