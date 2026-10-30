# Decision log

Short records of the important choices, newest first. Add a new entry whenever
a choice changes how the system works. Format: context, decision, consequence.

---

## D-017 · Public AI hostname ai001.sakir.bd behind Cloudflare
**Date:** 2026-10-31
**Context:** The previous public hostname did not reach the AI webhook. Sakir added
an A record for ai001.sakir.bd and explicitly chose to retain Cloudflare.
**Decision:** Use ai001.sakir.bd as PUBLIC_DOMAIN with a dedicated Nginx site and
valid origin certificate. Reuse existing public paths (/meta/webhook, /hooks/,
/public-media/). Do not expose internal APIs, admin pages or a generic /api/v1 proxy.
Keep unrelated sites intact. Record provisioning in scripts/setup-public-domain.sh.
**Consequence:** Meta callback becomes https://ai001.sakir.bd/meta/webhook after
verification. Existing external subscriptions must be updated separately. n8n's
container environment needs a separate refresh to adopt the new public URL.

## D-016 · Backup completion requires successful encryption and every product dump
**Date:** 2026-10-31
**Context:** The live nightly backup failed on GNU tar's status 1 when Grafana
changed during archiving. Review also found failed product hooks were ignored and
encryption wrote directly to a filename used by the freshness health check.
**Decision:** Serialize backups with flock, use private temporary files, treat tar
status 1 as a visible live-file consistency warning, and retain fatal errors as
failures. Every product hook must succeed. Encrypt inside the working directory
and publish the final archive by rename only after encryption succeeds.
**Consequence:** A partial encrypted output no longer appears fresh/complete.
Postgres dumps remain consistent; the live file archive is not a guarantee of
application-consistent SQLite state. Snapshotting, remote verification and restore
acceptance remain open in PROGRESS.md. This change does not alter owner approvals,
credentials, destinations or retention.

## D-015 · A web edit form for Sakir's own settings; Hermes' setup wizard dropped
**Date:** 2026-10-29
**Context:** The first real install stalled inside `docker compose run --rm hermes setup`
(the upstream interactive wizard): it logged into Nous's own hosted provider instead of
OpenRouter, defaulted to creating a brand-new Telegram bot instead of reusing the already
configured `@SakirAI_bot`, and crashed on Ctrl+C partway through `install.sh`. Separately,
Sakir asked for an easier way to change settings later than re-running the installer's
interactive prompts over SSH.
**Decision:**
- `step_hermes` no longer runs the wizard. It writes `data/hermes/config.yaml` itself (model
  only; Telegram and the OpenRouter key were already being read from `data/hermes/.env`, which
  the installer pre-seeds — confirmed against Hermes' own docs, which treat that `.env` as a
  full alternative to the wizard). A missing Hermes OpenRouter key is now asked for in
  `step_secrets` like every other key, instead of being silently skipped.
- New `settings-ui` service (`services/settings-ui/`), two pages behind one login:
  - `/` — a dashboard: the system's flow diagram, every container's state/health, the sales
    pipeline (leads by stage, messages, approvals waiting) and spend from dt-assistant's own
    `/internal/*` API, and how long ago the last backup ran. Read-only; still renders if
    dt-assistant itself is down or paused.
  - `/settings` — Telegram/OpenRouter/Meta tokens, sales budget, data retention, and which
    intents may auto-send. "Save" writes the same files `install.sh --step secrets` would,
    "Apply" runs `docker compose up -d --force-recreate <service>` so the change takes effect
    immediately.
  Reached over Tailscale or an SSH tunnel only, one HTTP Basic password (shown once at
  install, rotate with `sakir-ai settings-password`); never through the public Nginx.
  `autonomy.never_auto` is not a field on the page at all, and the server refuses to save an
  `auto_intents` list that overlaps it even if the request is hand-crafted — D-004 cannot be
  switched off by anyone who only has the Settings password.
- Trade-off, accepted deliberately: unlike every other container, settings-ui mounts the whole
  project directory read-write plus the Docker socket (needed to recreate a container with a
  freshly-written secret) — equivalent in reach to Sakir's own SSH/root access, not to an
  agent's. Domain/TLS/Nginx stay out of scope: those need real system commands this container
  should not run; `docs/OPERATIONS.md` still covers them.
**Consequence:** A fresh install no longer depends on an interactive upstream wizard behaving
a particular way over SSH. Changing a token, the budget, or which replies go out automatically
is now a form and one click — no SSH needed — but the settings-ui password is as sensitive as
root and must be treated that way.

## D-014 · Alerts that reach Sakir even when the server cannot
**Date:** 2026-10-29
**Context:** Uptime Kuma runs on the same server, so a dead server could not alert anyone;
backup failures were only written to a log; pending security reboots went unnoticed.
**Decision:**
- Backup failures send a Telegram message (`notify_telegram` in `lib/common.sh`).
- Optional outside monitor (healthchecks.io or any compatible service): a 5-minute heartbeat
  (`sakir-heartbeat.timer`, which also reports unhealthy core services) and start/success/fail
  pings from every backup. A missing ping = server down or backup not run.
- `reboot_required` is a read action for Hermes; health check and morning brief show it.
- Host log files rotate weekly (`/etc/logrotate.d/sakir-ai`).
- Customer data retention runs daily in dt-assistant (`retention:` in `dt-assistant.yaml`;
  default 12 months for messages and dead leads, 6 months for decided drafts), matching the
  privacy policy template Meta review requires.
- Optional `disks` step mounts an empty second disk (e.g. NVMe) at `data/`.
- GitHub Actions `ci` runs the AGENTS.md checks on every push, including a check that money
  and complaint intents can never be automatic; `main` should be protected to require it.
**Consequence:** Two free outside checks to create; deletions of old customer data are
automatic and permanent (backups keep them 14 more days).

## D-013 · DT products run natively on the host; Sakir AI stays in Docker; hostname sakir-ai-001
**Date:** 2026-10-29
**Context:** Sakir prefers DT production apps (DT Restora and later products) to run directly on
the server, not in Docker. On Linux, containers are not virtual machines: CPU and memory run at
native speed. The measurable costs are small and avoidable — Docker's bridge network/NAT adds
a little latency (host networking or a Unix socket removes it), heavy writes inside the
container's own filesystem are slower (volumes avoid it), and very chatty `json-file` logs cost
some I/O. The real gains of native for a Laravel/PHP stack are familiar tuning (PHP-FPM pools,
OPcache, MySQL buffer pool), direct systemd management and one less layer to debug at 3 a.m.
**Decision:**
- DT products run natively: Nginx (already on the host) → PHP-FPM / Node, with MySQL or
  PostgreSQL and Redis installed from apt, managed by systemd. Each product gets its own Nginx
  server block, database and system user.
- The Sakir AI stack stays in Docker: its containers are capped, isolated from production and
  are what keeps agents away from the host (safe-exec, no shell).
- Native services get resource priority over the AI stack: the AI containers already have hard
  CPU/RAM caps; production can additionally run in a systemd slice with a higher `CPUWeight`.
- The installer names the server `sakir-ai-001` (`SERVER_HOSTNAME`, set in the `system` step;
  cloud-init is told to keep it).
**Consequence:** A future `prod` installer step will add the native stack (versions to be
confirmed: PHP, database, Node). safe-exec's allowlist will gain `systemctl restart` actions
for these services, and `scripts/backup.d/` hooks will dump their databases with `mysqldump`
or `pg_dump` from the host instead of `docker exec`.

## D-012 · One rule file for every AI coding tool; the assistant is "Sakir AI 001"
**Date:** 2026-10-29
**Context:** Sakir wants to set up and fix the server with whichever AI app he has open —
Claude, ChatGPT/Codex, Grok or Gemini — and call his assistant "Sakir AI 001".
**Decision:** `AGENTS.md` holds all rules (read by Codex and Grok Build); `CLAUDE.md` and
`GEMINI.md` only import it. `scripts/install-ai-tools.sh` (installer step `aitools`, optional)
installs the four CLIs for the admin user with their official installers. Hermes introduces
itself as "Sakir AI 001"; customers still see "Datatech BD Assistant".
**Consequence:** Change rules in one place only. Each tool uses Sakir's own subscription or
key; nothing is stored by the installer.

## D-011 · Approvals by plain message, not a slash command
**Date:** 2026-10-29
**Context:** The blueprint said Sakir approves risky actions with `/confirm <id> <code>`.
Hermes registers its own Telegram command menu and may treat unknown slash commands as its own.
**Decision:** safe-exec asks Sakir to send `confirm <id> <code>` as a normal message;
the `devops-watch` skill turns that into the `/confirm` API call.
**Consequence:** Works whatever Hermes does with slash commands.

## D-010 · Only Facebook and Instagram post automatically
**Date:** 2026-10-29
**Context:** YouTube, LinkedIn, TikTok and X each need their own developer approval,
OAuth app or paid API access.
**Decision:** The publisher posts to Facebook and Instagram; for other platforms it sends
Sakir a ready-to-paste caption and media file at the scheduled time.
**Consequence:** One manual paste per post on those platforms until each API is set up.
Adding one = a new branch in `publisher_tick()` in `services/dt-assistant/app/pipeline.py`.

## D-009 · Sales pipeline is a tested Python service, not n8n workflows
**Date:** 2026-10-29
**Context:** The blueprint put the Facebook sales flow in n8n. Hand-written n8n exports are
fragile to import and cannot be unit-tested; this flow handles money questions for real customers.
**Decision:** `dt-assistant` (FastAPI + asyncpg) implements webhooks, classification, policy,
drafting, the approval bot, follow-ups, publishing and budgets, with 32 tests.
n8n stays installed for Sakir's own no-code automations.
**Consequence:** Changing sales behaviour means editing `config/dt-assistant.yaml`
(no code) or `app/policy.py` (code, with tests).

## D-008 · Two Telegram bots
**Date:** 2026-10-29
**Context:** One bot token can only be polled by one program.
**Decision:** @SakirAI_bot belongs to Hermes; @DTSalesDesk_bot belongs to dt-assistant.
**Consequence:** Customer approvals stay in their own clean chat, separate from conversations with Hermes.

## D-007 · Fresh server holds only the AI stack (for now)
**Date:** 2026-10-29
**Context:** The blueprint assumed DT production apps share the VPS. The install target is a fresh server.
**Decision:** The installer sets up only Sakir AI. DT products can be added later on their own
Docker network, with backup hooks in `scripts/backup.d/`.
**Consequence:** Resource caps leave ~3 vCPU / 29 GB free for DT products.

## D-006 · Backups encrypted with a key that is not on the server
**Date:** 2026-10-29
**Decision:** `age` public-key encryption; the private key is shown once at install and kept by Sakir.
Reboot and power off are blocked unless a backup from the last 24 hours exists.
**Consequence:** A stolen server or bucket does not expose data. Losing the private key means losing old backups.

## D-005 · safe-exec is the only path from agents to the server
**Date:** 2026-10-29
**Decision:** Named actions from `config/allowlist.yaml`, three tiers (read, safe, risky).
Risky actions need a code sent only to Sakir. Host actions go through a root runner that re-checks the action name.
**Consequence:** Agents cannot run arbitrary commands on the host; new abilities need an allowlist entry.

## D-004 · Money questions always go to Sakir
**Date:** 2026-10-29
**Decision:** `price`, `discount`, `order`, `complaint`, `legal`, `other` are in `never_auto`
and cannot be sent without approval. Automation grows from FAQs and demos after two clean weeks.
**Consequence:** Slower replies on price questions; no wrong price ever reaches a customer.

## D-003 · Models through OpenRouter, routed by task
**Date:** 2026-10-29
**Decision:** Gemini 2.5 Flash-Lite classifies, DeepSeek V3.2 drafts, Gemini 2.5 Flash handles
proposal-stage leads and complaints. Hard monthly cap ($26 for sales) with a holding-reply fallback.
**Consequence:** About $26/month at 600 customer turns/day. Prices checked quarterly.

## D-002 · Bangla speech on the server
**Date:** 2026-10-29
**Decision:** BanglaSpeech2Text `small` (Whisper fine-tuned for Bangla) for Bangla,
faster-whisper for language detection and English; Edge-TTS for spoken replies.
**Consequence:** No per-minute speech costs. Run the 50-clip test before switching to `large`.

## D-001 · Hermes Agent as the assistant runtime
**Date:** 2026-10-29
**Context:** OpenClaw and Hermes were both candidates.
**Decision:** Hermes (Nous Research, MIT) — Sakir's preference; persistent memory, skills,
Telegram gateway, official Docker image.
**Consequence:** Agents are skills in one Hermes, not separate servers.
