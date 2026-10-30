# Capability inventory and acceptance gates

This inventory maps the full vision to repository evidence at baseline `7e7d012`
(checked 2026-10-31, Asia/Dhaka). **Partial** means a foundation exists but the full
workflow is incomplete; **Planned** means the requested workflow has no complete
implementation. Code presence does not prove successful deployment. No new live
server verification was performed for this documentation update.

Existing implementation files are relative to the repository root. Candidate
integrations below are proposals, not installed dependencies or current provider
contracts. Consult official provider documentation during implementation before
choosing permissions, pricing or delivery rules.

## C01 — Agent roles and orchestration

**Status: Partial.** `hermes/skills/` contains ten role skills; `tools/sakir.py` dispatches tools. No durable multi-worker task scheduler or cross-agent task ledger is provided.

**Target workflow:** Sakir request or schedule → coordinator decomposes tasks → scoped role drafts → reviewer checks evidence → Sakir approves external actions → recorded result.

**Dependencies and boundaries:** Proposed task ledger with task/project IDs, owner, dependencies, input provenance, approval state, budget, retry count and terminal outcome; do not add a new service until needed.

**Acceptance gate:** Replay one multi-role task after a worker restart without duplicate external effects; cancellation stops pending steps and reports completed work.

## C02 — Autonomous software development and multiple projects

**Status: Planned.** `scripts/install-ai-tools.sh` and `docs/AI-TOOLS.md` install coding tools; they do not implement an autonomous issue-to-PR service.

**Target workflow:** Approved issue → project-scoped branch → implementation → tests and review → PR → owner merge → separately approved deployment.

**Dependencies and boundaries:** GitHub authorization scoped per repository, isolated build workers, per-project workspaces and staging credentials. No customer text becomes executable work.

**Acceptance gate:** Run two projects with isolated files/secrets; produce tested PRs, reject an out-of-scope repository, and recover an interrupted task without pushing to main.

## C03 — DevOps and production delivery

**Status: Partial.** `services/safe-exec/app.py`, `hostops/sakir-hostops`, monitoring configs and `devops-watch` provide bounded actions. Native DT product provisioning is pending.

**Target workflow:** Health event → read-only diagnosis → proposed remediation → required approval → named action → health verification and incident record.

**Dependencies and boundaries:** Future native prod step, staging, per-product database backup hooks and new reviewed allowlist actions; versions still need confirmation.

**Acceptance gate:** Show an alert and safe restart in staging; demonstrate rejected unknown actions and expired/wrong approval codes; prove backup restore before production deployment.

## C04 — Digital marketing and campaign strategy

**Status: Partial.** `content-pack` and `knowledge-templates/datatech/` support draft content; no campaign execution or experiment manager exists.

**Target workflow:** Approved product brief → audience hypotheses and sourced competitor research → campaign proposal → content calendar → approved execution → review against baseline.

**Dependencies and boundaries:** Proposed campaign IDs, objective, audience, channel, owner, approved budget and source links; use only public or authorized material.

**Acceptance gate:** Produce one reviewed campaign with factual claims, traceable sources, measurable objective and post-campaign results; reject unsupported claims.

## C05 — SEO and competitor research

**Status: Partial.** `content-pack` specifies an SEO page draft. No crawler, ranking tracker, Search Console ingestion or CMS publishing connector is supplied.

**Target workflow:** Approved domain/query → collect dated evidence → technical/content audit → prioritized changes → reviewed CMS or code change → measurement.

**Dependencies and boundaries:** Read-only analytics/search access first; domain ownership and CMS credentials before any write. Record crawl scope and source dates; provider selection pending.

**Acceptance gate:** Audit a test site, verify each finding against evidence, publish only an approved change, and compare a defined baseline without promising rankings.

## C06 — Lead discovery and market research

**Status: Planned.** Existing leads are inbound Meta contacts in `schema.sql`; there is no outbound prospect discovery connector.

**Target workflow:** Define market and inclusion criteria → research public business sources → deduplicate → score with reasons → owner review → approved CRM import.

**Dependencies and boundaries:** Proposed source URL/date, business contact provenance, consent/contact basis and suppression status; no bulk unsolicited outreach.

**Acceptance gate:** Export a reviewed sample with source evidence, duplicate detection and suppression handling; prove importing does not trigger contact automatically.

## C07 — Social copy, graphics and product books

**Status: Partial.** `content-pack` writes post copy, reel scripts, SEO copy and a product-book outline. It does not supply an image renderer or finished PDF generator.

**Target workflow:** Facts and brand brief → copy/storyboard → generated or supplied visual → layout/export → factual and visual review → approval.

**Dependencies and boundaries:** Choose image/document tooling later; record asset rights, fonts, source facts, version and owner approval; preserve Bangla glyphs in exports.

**Acceptance gate:** Deliver a complete Bangla/English pack with readable exports, no TODO prices, licensed assets and approved captions; outline-only output fails the finished-book gate.

## C08 — Video, reels and voiceover generation

**Status: Planned.** Reel scripts exist as skill output; no video rendering, editing, subtitle alignment or upload worker is implemented.

**Target workflow:** Approved script → storyboard and assets → voiceover → render → subtitles/music → preview → approval → supported publishing or manual handoff.

**Dependencies and boundaries:** Rendering worker with CPU/time limits, storage lifecycle and cost estimate; media provider, music license and voice consent remain unresolved.

**Acceptance gate:** Produce one reviewed 30-second Bangla reel with aligned captions, approved claims and usable export; failed render retries do not publish or bill indefinitely.

## C09 — Social media management

**Status: Partial.** `pipeline.py:publisher_tick` and `content_calendar` implement Facebook/Instagram publishing and other-platform reminders. Meta comments/inbox support is a foundation, not universal moderation.

**Target workflow:** Approved calendar entry → due job → platform-specific publishing or reminder → result/error → owner follow-up.

**Dependencies and boundaries:** Additional platforms require separate OAuth/API adapters and capability checks; proposed asset approval/version tracking and per-platform moderation rules.

**Acceptance gate:** Demonstrate Facebook/Instagram delivery with permitted test accounts; other platforms produce reminders only; simulate timeout and reconcile remote state before retry.

## C10 — Chat automation and channel expansion

**Status: Partial.** `app/main.py`, `meta.py` and `pipeline.py` support Meta customer webhooks. Telegram serves Sakir and approvals; no WhatsApp or website customer adapter exists.

**Target workflow:** Verified inbound event → normalized channel identity → dedupe → policy and knowledge → draft/approval → channel send → delivery record.

**Dependencies and boundaries:** Future WhatsApp and website adapters need verified auth, explicit identity linking, consent, per-channel delivery windows and human handoff. Do not assume Meta rules apply identically to every channel.

**Acceptance gate:** Test each adapter independently for forged events, duplicates, identity collisions, expired delivery windows and human escalation before enabling it.

## C11 — AI sales and CRM

**Status: Partial.** `schema.sql` has leads, messages, approvals and pipeline stages; `pipeline.py` drafts replies/follow-ups. No external CRM or calendar booking connector is provided.

**Target workflow:** Inbound inquiry → qualify business need → reviewed demo proposal → confirmed slot → stage update → consented follow-up → won/lost review.

**Dependencies and boundaries:** Proposed CRM mapping and calendar availability checks, contact consent and owner assignment. Never invent a booking, payment, quote or contract.

**Acceptance gate:** Complete a test lead journey with consistent history; money/order intents always require approval; conflicting calendar slots and opt-outs block automated follow-up.

## C12 — Customer support

**Status: Partial.** FAQ policy, knowledge retrieval and complaint escalation are reusable foundations. No ticket queue, service-level tracking or product diagnostic connector exists.

**Target workflow:** Inquiry → approved troubleshooting knowledge → scoped response → unresolved/complaint handoff → ticket owner → confirmed resolution.

**Dependencies and boundaries:** Proposed ticket ID, severity, product, assigned owner and response target; diagnostics read-only and customer-scoped. Refunds and complaints stay human-owned.

**Acceptance gate:** Resolve known test FAQs, escalate unknown/complaint cases with history, and show cross-customer data cannot appear in replies; never close a ticket solely on model confidence.

## C13 — Paid advertising

**Status: Planned.** No ad account connector, budget mutation or ad publishing implementation exists.

**Target workflow:** Research → draft creative/audience → forecast with assumptions → Sakir approves exact campaign and spend → limited launch → read-only monitoring → reviewed adjustment.

**Dependencies and boundaries:** Select provider/account, permissions and reporting adapter later. Separate ad spend from model costs; approval binds account, creative, audience, time range and hard cap.

**Acceptance gate:** Use a sandbox or dry run first; expired approval, cap breach and duplicate launch are blocked; emergency stop verified before any real spend.

## C14 — Business analytics and reporting

**Status: Partial.** `spend`, `metrics`, `summary` and settings dashboard report local sales activity and model spend. No revenue attribution or cross-platform warehouse exists.

**Target workflow:** Collect authorized metrics → normalize periods/currency → reconcile → dashboard/brief → owner decision.

**Dependencies and boundaries:** Proposed source-specific read-only adapters, metric dictionary, attribution assumptions and freshness timestamps; distinguish leads from paid revenue.

**Acceptance gate:** Reconcile a sample report against source records; flag stale/missing data, explain attribution and prevent double-counting across channels.

## C15 — Persistent memory and continuous improvement

**Status: Partial.** `remember` writes a knowledge inbox; indexer/Qdrant retrieve knowledge; Hermes stores memory. No autonomous training or validated self-modification pipeline exists.

**Target workflow:** New fact/feedback → provenance and owner review → canonical knowledge update → reindex → regression evaluation → versioned release.

**Dependencies and boundaries:** Separate personal, product and operations knowledge; define retention/deletion and conflict resolution. Retrieved text is untrusted data, never authorization.

**Acceptance gate:** A corrected fact replaces stale retrieval, deleted material disappears after reindex, and customer text cannot change pricing, policies or agent permissions.

## C16 — Personal assistance, career and learning

**Status: Partial.** `daily-brief`, `career-scout`, `linkedin-writer`, `learning-coach`, `voice-notes` and persona skills provide instructions; schedules and real outcomes need operator verification.

**Target workflow:** Owner request/schedule → approved personal knowledge → draft brief, shortlist, learning plan or appointment proposal → owner review.

**Dependencies and boundaries:** Future email/calendar connectors need least privilege and explicit send/write approval; never auto-submit applications or fabricate achievements.

**Acceptance gate:** Deliver seven days of briefs with sources and actual outstanding work; draft a factual CV and demonstrate no application or message sends without authorization.

## C17 — Workflow automation and proactive execution

**Status: Partial.** n8n is installed and systemd/service schedules exist. No supplied library of connected business workflows or global workflow stop exists.

**Target workflow:** Authorized trigger → scoped workflow → bounded retries → proposed external effect → approval where required → execution record → actionable alert.

**Dependencies and boundaries:** Proposed workflow inventory with owner, credentials, trigger, budget, timeout and disable procedure; isolate sales from unrelated n8n workflows.

**Acceptance gate:** Exercise one scheduled workflow through success, dependency failure, duplicate event and cancellation; notify on actionable failure without alert loops.

## C18 — Live voice and video

**Status: Planned.** `services/stt/` and `services/tts/` handle speech requests, not streaming calls; no real-time media layer is installed.

**Target workflow:** Private authenticated call → streaming media → transcription → assistant response → speech; optional video only after consent → explicit end and cleanup.

**Dependencies and boundaries:** Choose a media layer only after a pilot; measure Dhaka latency, concurrency and cost/minute. Define recording consent and retention; no impersonation or customer calling as Sakir.

**Acceptance gate:** Private pilot handles interruption, packet loss and termination; measured latency/cost meet owner-approved limits; no recording without consent. Customer rollout remains a separate gate.

