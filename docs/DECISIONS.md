# Decision log

Short records of the important choices, newest first. Add a new entry whenever
a choice changes how the system works. Format: context, decision, consequence.

---

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
