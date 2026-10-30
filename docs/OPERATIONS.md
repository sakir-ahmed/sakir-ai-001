# Operations guide

How to run Sakir AI 001 after it is installed: routines, incident playbooks,
updates and restores. Commands assume you are logged in as `sakir` on the server.

## Routines

### Daily (5 minutes)
- Read the 08:30 morning brief and the 21:30 evening summary on @SakirAI_bot.
- Clear @DTSalesDesk_bot: approve, edit or reject every draft (they expire after 24 hours).
- Act on any alert (site down, angry customer, spend warning, approval code).

### Weekly (Friday, 30 minutes)
- [ ] Review 20 customer replies: `/stats` in @DTSalesDesk_bot, then scroll the sent cards.
      Note the edit rate (target: under 20%).
- [ ] Fix what the edits show: add facts to `knowledge/`, add FAQ templates, tune `sales/prompt.md`.
- [ ] `sakir-ai reindex` if knowledge changed.
- [ ] Check spend: ask Hermes "how much did AI cost this month?".
- [ ] Review next week's content calendar: ask Hermes "content calendar for 7 days".
- [ ] Move `/remember` notes from `knowledge/inbox/` into the right files.

### Monthly (first Sunday, 1 hour)
- [ ] Restore test on your laptop (see "Restore" below). Record the result in [ROADMAP.md](ROADMAP.md).
- [ ] `sakir-ai update` (it backs up first). Read release notes for Hermes and n8n before.
- [ ] `sakir-ai health` → everything PASS.
- [ ] Disk: `df -h /` under 70%; `sudo ncdu /opt/sakir-ai/data` if not.
- [ ] Check OpenRouter prices for the three models in `config/dt-assistant.yaml`.
- [ ] Decide on autonomy changes (below).

### Security updates and reboots
Updates install automatically every day; some (kernel, OpenSSL) need a reboot to take
effect. When one is pending, `sakir-ai health` and the morning brief say so. Reboot at a
quiet hour (e.g. 04:00) through Hermes ("reboot the server") — it needs your code and a
backup from the last 24 hours. Check after: `sakir-ai health`.

### Every 6 months
- [ ] Rotate keys with [`scripts/rotate-keys.md`](../scripts/rotate-keys.md).
- [ ] Check the Meta Graph API version in `config/dt-assistant.yaml` is still supported.
- [ ] Remove unused Telegram sessions and Tailscale devices.

## Dashboard and Settings page (one browser tab, no SSH)

Reach it at `http://127.0.0.1:8090`:
- Over Tailscale (if `install.sh --step tailscale` was run): `https://<server-name>.<tailnet>.ts.net:8446`
- Otherwise, an SSH tunnel from your laptop: `ssh -L 8090:127.0.0.1:8090 sakir@<server-ip>`,
  then open `http://127.0.0.1:8090` in your own browser.

Log in as `sakir`; the password was printed once during install
(`sudo bash install.sh --step secrets` to see it again if that scrollback is gone, or
`sakir-ai secret SETTINGS_UI_PASSWORD`). To rotate it: `sakir-ai settings-password`.

**`/` — Dashboard.** The whole system on one page: a flow diagram of how everything connects
(Telegram ↔ Hermes ↔ safe-exec ↔ host; Meta ↔ dt-assistant ↔ ai-db ↔ the approvals bot), every
container's state and health, today's lead pipeline and message/approval counts, this month's
sales spend against budget, the approvals currently waiting for you, and how long ago the last
backup ran. If dt-assistant is paused, restarting, or not configured yet, that section just
says so instead of breaking the page.

**`/settings` — the edit form.** Telegram tokens, OpenRouter keys, Meta/Instagram credentials,
the sales budget, data retention, and which reply intents may send without your approval — then
restarts only the affected container. It never shows a secret's current value (same "blank
keeps it" rule as the installer), and it cannot be used to make
`price`/`discount`/`order`/`complaint`/`legal` automatic, whatever is typed into it. Domain,
Nginx and TLS are not on this page — see "Updating" above for those; they need real root
commands this page does not run.

Treat the password like the server's root password: whoever has it can see which secrets are
set, read the sales pipeline, and restart Hermes, dt-assistant or safe-exec.

## Raising autonomy

Move one step at a time, only after two weeks with an edit rate under 20% for that intent.

| Step | Change in `config/dt-assistant.yaml` | Effect |
| --- | --- | --- |
| 0 (start) | `auto_intents: []`, `auto_send_templates: false` | Everything is a draft |
| 1 | `auto_send_templates: true` | Saved FAQ answers go out automatically |
| 2 | `auto_intents: [faq]` | AI-written FAQ answers go out when confidence ≥ 0.85 |
| 3 | `auto_intents: [faq, demo, greeting]` | Demo requests answered automatically |

Never add `price`, `discount`, `order`, `complaint` or `legal`: they are in `never_auto`
and stay with you. After each change: `sakir-ai restart dt-assistant`.

## Incident playbooks

### Customers are not getting replies
1. `sakir-ai health` — is dt-assistant running and healthy?
2. `sakir-ai logs dt-assistant` — look for `bad signature`, `Graph`, `OpenRouter`, `budget`.
3. `curl -s -o /dev/null -w '%{http_code}\n' https://<domain>/meta/webhook` → should print `403`.
   `000` = DNS/TLS/Nginx problem: `sudo nginx -t`, `sudo systemctl status nginx`.
4. Meta → App → Webhooks: subscription active, Page subscribed, no delivery errors.
5. Page token expired? Generate a new long-lived token, then
   `sudo bash /opt/sakir-ai/install.sh --step secrets && sakir-ai restart dt-assistant`.
6. While fixing: `sakir-ai pause` sends holding replies so nobody is ignored.

### A wrong reply went to a customer
1. `sakir-ai pause` (or `/pause` in @DTSalesDesk_bot).
2. Reply to the customer personally from Meta Business Suite.
3. Find the cause: missing fact (add to knowledge), bad template, or the intent was automatic
   (remove it from `auto_intents`).
4. Add the message to your test set, then `sakir-ai resume`.

### Spend is climbing fast
1. Ask Hermes "how much did AI cost this month?" — which purpose is high?
2. Spam or loops: check `sakir-ai logs dt-assistant` for repeated leads; block the user on the Page.
3. Lower `budget.monthly_usd` or switch `models.reply.id` to a cheaper model; restart dt-assistant.
4. OpenRouter key limits are the hard stop; check them at openrouter.ai.

### Hermes does not answer
1. `sakir-ai logs hermes`.
2. `TELEGRAM_ALLOWED_USERS` in `/opt/sakir-ai/data/hermes/.env` must be your numeric ID.
3. OpenRouter key valid and has credit?
4. `sakir-ai restart hermes`.

### Server is slow or a container keeps restarting
1. `sakir-ai status` — which container uses the CPU/RAM?
2. stt is the usual peak (transcribing long audio); it is capped at 2 vCPU.
3. Memory kills: `sudo dmesg -T | grep -i oom`. Raise that service's `mem_limit` in
   `compose.yml` only if the server has room, then `sakir-ai start`.

### Outside monitor alerted (healthchecks.io)
- **Heartbeat down:** the server is off, unreachable, or the core is unhealthy (the alert
  body lists what failed). Try SSH; if it does not answer, use the provider's web console;
  if the server is gone, follow "Full restore" below.
- **Backup missed or failed:** `sudo journalctl -u sakir-backup -n 50`; run `sakir-ai backup`
  and watch it. Telegram also got the failure line.

### Moving data/ to a second disk later
The `disks` installer step only formats an empty disk while `data/` is empty. To move an
existing install: `sakir-ai backup`, `sakir-ai stop`, mount the new disk at `/mnt/newdata`,
`sudo rsync -aHAX /opt/sakir-ai/data/ /mnt/newdata/`, change the mount point in `/etc/fstab`
to `/opt/sakir-ai/data` (after renaming the old folder to `data.old`), `sudo mount -a`,
`sakir-ai start`, `sakir-ai health`; delete `data.old` only after a week of normal running.

### Disk almost full
1. `sudo ncdu /opt/sakir-ai` — usually `backups/`, `data/loki`, or Docker images.
2. `docker image prune -f`; old backups: lower `KEEP_DAYS` in `scripts/backup.sh`.
3. Loki keeps 30 days; lower `retention_period` in `config/loki.yaml` if needed.

### Suspected leak or break-in
1. `sakir-ai pause` and `sakir-ai stop hermes`.
2. Rotate every key in [`scripts/rotate-keys.md`](../scripts/rotate-keys.md), Telegram tokens first.
3. Check `/var/log/auth.log`, `sudo fail2ban-client status sshd`,
   `/opt/sakir-ai/data/safe-exec-audit/actions.log`.
4. If unsure, rebuild: fresh server + restore (below).

## Updating

```bash
sakir-ai update        # backup → pull images → rebuild our services → restart → reinstall skills
sakir-ai health
```

Pin versions after a good update so the next one is deliberate:
```bash
sakir-ai versions      # shows the images in use
sudo nano /opt/sakir-ai/.env    # e.g. N8N_IMAGE=n8nio/n8n:<version>
```

Rollback: set the previous tag in `.env`, then `sakir-ai start`.

Updating the installer code itself:
```bash
cd ~/sakir-ai-001 && git pull
sudo bash install.sh --step layout     # copies new code to /opt/sakir-ai (never touches data or secrets)
sudo bash install.sh --step stack      # rebuilds and restarts
```

## Backup completion and progress

Track active recovery work in [PROGRESS.md](PROGRESS.md). Concurrent backups are
rejected. Fatal archive errors, failed product dump hooks and encryption failures
fail the run; incomplete encrypted output never becomes a final backup filename.
GNU tar status 1 logs a warning because live files changed. Such a backup still
needs a restore drill and is not an application-consistent SQLite snapshot.
Local success without an off-site copy is not disaster-recovery completion.

## Restore

### Test (monthly, on your laptop)
```bash
scripts/restore-test.sh sakir-ai_<date>_0300.tar.age ~/keys/sakir-backup.key
```
It decrypts, loads ai-db into a throwaway Postgres and prints row counts.

### Full restore onto a new server
1. Install the bundle on the new server: `sudo bash install.sh` (same domain; it creates fresh secrets —
   these are replaced in step 4).
2. Stop everything: `sakir-ai stop`.
3. Copy the backup and your private key to the server, then:
   ```bash
   mkdir -p /root/restore && cd /root/restore
   age -d -i sakir-backup.key sakir-ai_<date>.tar.age | tar -xf -
   tar -xzf files.tgz -C /opt/sakir-ai        # config, secrets, .env, knowledge, data/hermes, kuma, grafana
   ```
4. Load the databases (the restored secrets now match the dumps):
   ```bash
   cd /opt/sakir-ai
   sudo rm -rf data/ai-db data/n8n-db          # empty databases from step 1
   docker compose up -d ai-db n8n-db && sleep 15
   gunzip -c /root/restore/ai-db.sql.gz  | docker compose exec -T ai-db  psql -U sakirai -d postgres
   gunzip -c /root/restore/n8n-db.sql.gz | docker compose exec -T n8n-db psql -U n8n -d postgres
   ```
   Messages that a role or database "already exists" are expected; the tables and rows still load.
5. `sakir-ai start && sakir-ai reindex && sakir-ai health`.
6. Point DNS to the new server if the IP changed, then `sudo bash install.sh --step tls`.

## Where to look

| Question | Place |
| --- | --- |
| What did agents do on the server? | `/opt/sakir-ai/data/safe-exec-audit/actions.log` |
| What did the installer do? | `/var/log/sakir-ai-install.log` |
| Host actions (reboot, nginx, ssl) | `/var/log/sakir-hostops.log` |
| Backup runs | `/var/log/sakir-ai-backup.log`, `journalctl -u sakir-backup` |
| Heartbeat | `journalctl -u sakir-heartbeat`, and the healthchecks.io dashboard |
| Container logs (30 days) | Grafana → Explore → Loki → `{container="dt-assistant"}` |
| Sales data | ai-db tables `leads`, `messages`, `approvals`, `content_calendar`, `spend`, `metrics` |
