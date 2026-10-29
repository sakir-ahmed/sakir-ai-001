# Roadmap and progress

Tick items as they are done (edit this file on GitHub or in your clone). Dates are
the plan from the blueprint; move them if needed and note why in DECISIONS.md.

## Status

| Phase | Planned | Status |
| --- | --- | --- |
| 0 Build the installer | Oct 2026 | Done — this repo |
| 1 Foundation | Nov 2–8 | Not started |
| 2 Command center | Nov 9–22 | Not started |
| 3 Sales agent (drafts) | Nov 16 – Dec 6 | Not started |
| Gate: FAQ replies automatic | Dec 7 | — |
| 4 Content factory | Dec 7–20 | Not started |
| 5 DevOps watcher | Dec 21–27 | Not started |
| 6 Career and branding | Dec 28 – Jan 10 | Not started |
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
- [ ] Run `sudo bash install.sh` on the server
- [ ] Save the backup private key in the password manager
- [ ] Optional: AI coding tools (`--step aitools`); log in to each once (docs/AI-TOOLS.md)
- [ ] Set @SakirAI_bot display name to "Sakir AI 001" in @BotFather
- [ ] Configure rclone remote `sakir-backup`; confirm a backup uploads
- [ ] First restore test passes
- [ ] Fill `knowledge/me/` (profile TODOs, voice with 10 real examples, likes-dislikes, goals)
- [ ] Fill `knowledge/datatech/company.md`, `brand.md`, `case-studies.md`
- [ ] Fill DT Restora `features.md`, `pricing.md`, `faq.md`

## Phase 2 — Command center (Nov 9–22)
- [ ] Hermes answers on Telegram; stranger gets no reply
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
