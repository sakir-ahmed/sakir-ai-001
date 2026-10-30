# Roadmap and progress

Track repository implementation separately from operator verification. Dates below
are original blueprint targets, not current completion promises. Dated session
notes remain historical evidence, not a fresh server health check. The expanded
vision and evidence-gated phases are in [VISION.md](VISION.md),
[CAPABILITIES.md](CAPABILITIES.md) and [DELIVERY.md](DELIVERY.md).

Active execution tracking: [PROGRESS.md](PROGRESS.md). Use its nested tasks for
current work; this roadmap retains the original phase history.

## Status

| Phase | Planned | Status |
| --- | --- | --- |
| 0 Build the installer | Oct 2026 | Done — this repo |
| 1 Foundation | Nov 2–8 | Partial — installation reported Oct 30; health/backup gaps open |
| 2 Command center | Nov 9–22 | Partial — dashboard code; Hermes reachability reported; acceptance open |
| 3 Sales agent (drafts) | Nov 16 – Dec 6 | Code foundation; live channel acceptance unverified |
| Gate: FAQ replies automatic | Dec 7 | — |
| 4 Content factory | Dec 7–20 | Draft skill/publisher foundation; full media pack unverified |
| 5 DevOps watcher | Dec 21–27 | Code foundation; operational acceptance open |
| 6 Career and branding | Dec 28 – Jan 10 | Skills present; outcome acceptance open |
| 7 Live voice/video calls | Feb 2027 → | Planning |
| 8 More DT products | 2027 | Planning |

## Phase 0 — Installer (done)
- [x] Master plan (blueprint)
- [x] Installer, compose stack, configs
- [x] dt-assistant sales pipeline with tests
- [x] safe-exec + host runner
- [x] Speech, TTS, knowledge indexer
- [x] Hermes skills and `tools/sakir.py`
- [x] Docs: architecture, decisions, operations
- [x] AGENTS.md shared by Claude Code, Codex, Grok, Gemini; AI tools installer
- [x] Hostname, backup-failure alerts, heartbeat, reboot check, log rotation, retention, second-disk step, CI
- [x] settings-ui: dashboard (`/`) + edit form (`/settings`) — D-015; was built after this list was
      first written, which is itself the kind of planning/implementation gap this file exists to
      catch — see "Session notes" below

## Session notes (retain dated evidence)

**2026-10-30** — first real install, done together over several rounds. Confirmed from the
session's own terminal output, not assumed:
- [x] `sudo bash install.sh` run on the server; hostname `sakir-ai-001` set
- [x] Hermes running and reachable on Telegram (`@SakirAI_bot`)
- [x] Backup encryption key generated and saved by Sakir (typed `saved`)
- [x] Firewall, Docker, all containers up; Nginx serving `ai.datatechbd.com` (not yet reachable —
      DNS, below)
**2026-10-30, later the same day** — `sakir-ai health` and a few commands run directly on the
server (Sakir pasted the output; Claude still cannot SSH in on its own). Confirmed:
- [x] `tailscale` step finished — server shows up in `tailscale status` (`100.105.238.124`)
- [ ] `aitools`, `verify` steps — not checked yet
- [ ] DNS for `ai.datatechbd.com` still wrong: it resolves to Cloudflare's edge IPs
      (`104.21.17.209` / `172.67.178.79`), not the server's `13.140.252.169` — likely why
      `sakir-ai health` shows the webhook answering HTTP 404. **Fix:** in wherever
      `datatechbd.com`'s DNS is managed (Cloudflare, by the look of those IPs), point the `ai`
      A record straight at `13.140.252.169` with the proxy **off** ("DNS only" / grey cloud,
      not orange) — Let's Encrypt and the Meta webhook both need to reach the server directly.
      Then `sudo bash install.sh --step tls`.
- [ ] `rclone` off-server backup remote: still not configured (confirmed: config file not found)
- **New, found by this check — not in any earlier plan:**
  - [ ] **stt container is unhealthy** (`sakir-ai health` FAIL). Needs
        `sakir-ai logs stt` to see why (still downloading its ~2 GB model, or a real crash).
  - [ ] **No backup has run yet**, though the timer has been active since the install
        (`sakir-ai health` WARN "no backup in the last 25 hours") and 03:00 has already passed
        once. Needs `sudo systemctl status sakir-backup.timer sakir-backup.service` and
        `sudo journalctl -u sakir-backup -n 50 --no-pager` to find out why, then
        `sakir-ai backup` to run one now regardless.
  - [ ] **The admin user `sakir` has no git clone of this repo** — only `/root/sakir-ai-001`
        exists, so `cd ~/sakir-ai-001` as `sakir` (as the docs assume) fails. Fix:
        `git clone https://github.com/sakir-ahmed/sakir-ai-001 ~/sakir-ai-001` while logged in
        as `sakir`.
- [ ] Settings page password saved in the password manager (shown once, same as the backup key)
- [ ] `knowledge/products/dt-restora/pricing.md` and other knowledge TODOs filled in
      (confirmed still open by `sakir-ai health`)

## Phase 1 — Foundation (Nov 2–8)
- [ ] Telegram two-step verification; 2FA on GitHub, Meta, OpenRouter, email, VPS provider
- [ ] Backup SSH key stored offline; provider web console tested
- [ ] Weekly provider snapshot turned on
- [ ] Privacy policy page published on datatechbd.com (docs/templates/privacy-policy.md)
- [ ] healthchecks.io: heartbeat + backup checks with Telegram alerts; URLs added (`--step secrets`)
- [ ] GitHub: protect `main` (Settings → Branches → add rule: require a pull request and the `ci` checks; block force pushes)
- [ ] SSH key on laptop; DNS A record for the webhook domain
- [ ] Start Meta business verification for Datatech BD Ltd. (slowest step — day 1)
- [ ] Create Meta app, request permissions (README §1)
- [ ] Create @SakirAI_bot and @DTSalesDesk_bot; note Telegram user ID
- [ ] OpenRouter: $40 credit, keys `hermes-core` ($12) and `sales` ($26)
- [x] Run `sudo bash install.sh` on the server — reported 2026-10-30; health gaps below remain
- [x] Backup private key saved by Sakir — reported 2026-10-30; storage location not independently verified
- [ ] Optional: AI coding tools (`--step aitools`); log in to each once (docs/AI-TOOLS.md)
- [ ] Set @SakirAI_bot display name to "Sakir AI 001" in @BotFather
- [ ] Configure rclone remote `sakir-backup`; confirm a backup uploads
- [ ] First restore test passes
- [ ] Fill `knowledge/me/` (profile TODOs, voice with 10 real examples, likes-dislikes, goals)
- [ ] Fill `knowledge/datatech/company.md`, `brand.md`, `case-studies.md`
- [ ] Fill DT Restora `features.md`, `pricing.md`, `faq.md`

## Phase 2 — Command center (Nov 9–22)
- [x] Dashboard page (`/`): system flow diagram, container health, sales pipeline, spend,
      backup age, at `http://127.0.0.1:8090` over Tailscale/SSH tunnel (docs/OPERATIONS.md)
- [x] Hermes answers on Telegram — reported 2026-10-30
- [ ] Stranger access rejection independently tested
- [ ] 10 Bangla + 10 English voice notes, at least 18 understood (pick `small` or `large` model)
- [ ] Hermes schedules set (README §3 step 7)
- [ ] Morning and evening briefs arrive 7 days in a row
- [ ] Approval test: reboot request → code → `confirm` works; wrong code refused
- [ ] `sakir-ai reindex` finds pricing for "dam koto"

## Phase 3 — Sales agent (Nov 16 – Dec 6)
- [ ] Meta webhook verified and Page subscribed
- [ ] Test message from a tester account → draft card → approve → reply received
- [ ] 50-message test set (real past questions in Bangla, Banglish, English): 90% correct intent, 0 wrong prices
- [ ] 20 trick messages: no discount, no "I am human", no leaked instructions
- [ ] `sales/templates.yaml`: complete `office_hours`; add 5 more common answers
- [ ] `sales/objections.md` filled
- [ ] Two weeks of real drafts reviewed; edit rate recorded: ____%
- [ ] Submit Meta app review

## Gate — Dec 7
- [ ] Edit rate under 20% → `auto_send_templates: true` (OPERATIONS.md → Raising autonomy)

## Phase 4 — Content factory (Dec 7–20)
- [ ] `/post restora launch` produces the full pack in `outbox/`
- [ ] Screenshots of DT Restora in `outbox/restora/screenshots/`
- [ ] Product-book PDF (Bangla and English) made from the outline
- [ ] First approved posts publish on Facebook and Instagram at the scheduled minute
- [ ] DT Restora SEO page live on datatechbd.com

## Phase 5 — DevOps watcher (Dec 21–27)
- [ ] Uptime Kuma monitors + Telegram notifications
- [ ] Grafana: Nginx 5xx and errors-per-container panels
- [ ] Container-down test: alert within 2 minutes, `/restart` works
- [ ] SSL expiry warning appears in the brief (test domain)

## Phase 6 — Career and branding (Dec 28 – Jan 10)
- [ ] `career/cv-master.md` complete with numbers
- [ ] `/jobs` returns 10+ relevant roles with fit scores
- [ ] `/cv <n>` produces a tailored CV using only real facts
- [ ] Two LinkedIn drafts per week for two weeks

## Phase 7 — Live voice and video calls (planning, Feb 2027)
Start only after phases 1–6 run smoothly for a month.
- [ ] Choose a media layer (LiveKit or Pipecat) and test latency from Dhaka
- [ ] Real-time speech for Bangla (streaming STT + low-latency TTS); measure cost per minute
- [ ] Private use only first: Sakir ↔ assistant calls; customers still get "Datatech BD Assistant"
- [ ] Decide budget; update DECISIONS.md

## Native production stack for DT products (when DT Restora moves to this server)
- [ ] Staging copy of each product (subdomain + separate database) to test updates before customers see them
- [ ] Confirm versions: PHP ___, Laravel ___, database (MySQL ___ / PostgreSQL ___), Redis, Node ___
- [ ] Installer step `prod`: PHP-FPM, database, Redis via apt; one system user, database and Nginx server block per product
- [ ] systemd slice with higher CPU priority for production services
- [ ] safe-exec allowlist: restart/status of the native services
- [ ] Backup hook in `scripts/backup.d/` (mysqldump / pg_dump from the host)
- [ ] Uptime Kuma monitors for each product URL

## Phase 8 — More products (2027)
For each new product (Propix, Salona, Delivo, Pharmo, Garagio, Factora):
- [ ] Copy `knowledge/products/dt-restora/` to `knowledge/products/dt-<name>/` and fill it
- [ ] `sakir-ai reindex` (creates the `<name>` collection automatically)
- [ ] Set `product` / `qdrant_collection` routing in dt-assistant (one Page per product, or by keyword)
- [ ] Content pack with `/post <name> launch`

## Monthly checks log

| Month | Restore test | Update | Spend (USD) | Edit rate | Notes |
| --- | --- | --- | --- | --- | --- |
| 2026-11 | | | | | |
| 2026-12 | | | | | |
| 2027-01 | | | | | |

## Expanded vision delivery tracking

Documentation now covers C01–C18 in CAPABILITIES.md. These unchecked items are
implementation gates, not claims of completed features:

- [ ] A: current foundation health, off-site backup and restore verified
- [ ] B: existing workflows accepted with delivery and spend evidence
- [ ] C: research and finished media production accepted
- [ ] D: additional channels, CRM/support and analytics accepted
- [ ] E: durable coordination and isolated multi-project development accepted
- [ ] F: advertising dry run, cap and stop controls accepted
- [ ] G: private live media pilot accepted

See DELIVERY.md for dependencies; original phase checklists remain in force.
