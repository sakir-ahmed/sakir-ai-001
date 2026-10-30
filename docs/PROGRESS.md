# Implementation progress — Sakir AI 001

This is the active nested checklist for closing the gap between goals and live
implementation. Update this file after each verified result. A checked parent
means all its children and acceptance evidence are complete. Code merged, deployed,
and live acceptance are separate milestones. Owner: Sakir; implementation: Sakir AI 001.

Last audit: 2026-10-31, approximately 02:27 Asia/Dhaka, through Termius.
Scope: read-only live audit plus repository evidence. No percentage is claimed.

## P0 — Recovery and alerts (in progress)

- [ ] R1 Reliable local encrypted backups
  - [x] Diagnose failed timer: tar exited after live Grafana files changed
  - [x] Reproduce archive warning, partial encryption and ignored hook failures
  - [x] Fix handling: warn on tar status 1, fail on fatal archive errors
  - [x] Publish final archive only after successful encryption
  - [x] Exclude encrypted output from outer archive; regression added after live run
  - [x] Fail whole backup when a product dump hook fails
  - [x] Serialize concurrent backup runs and restrict temporary file permissions
  - [x] Add six isolated regression cases and run them successfully
  - [ ] Merge reviewed fix into main
  - [x] Deploy backup script without changing secrets or other services — targeted script replacement; rollback copy retained
  - [x] Run live backup and verify completed encrypted archive — 2026-10-31 02:35 Dhaka, `sakir-ai_2026-10-31_023444.tar.age`, 167 MB; live-file consistency warning retained
  - [ ] Next scheduled timer run succeeds
  - [ ] Application-consistent SQLite snapshots for live state (current tar warning is not this guarantee)
- [ ] R2 Off-site copy and recovery proof
  - [x] Confirm no encrypted archive found during live audit
  - [x] Confirm root default rclone configuration absent
  - [ ] Deferred by Sakir (2026-10-31): select backup destination/account and configure credentials privately; local-only recovery risk accepted for now
  - [ ] Verify remote upload and independent retrieval
  - [ ] Restore archive on isolated environment using owner's private key (never put key on server)
  - [ ] Validate both databases, files, permissions and application state
  - [ ] Record recovery duration and retention policy
- [ ] R3 Alerts actually reach owner
  - [x] Confirm backup failure log also reports failed Telegram alert
  - [ ] Diagnose credential/delivery failure using redacted results only
  - [ ] Verify owner receives a test notification
  - [ ] Verify outside monitor observes success and failure; configured URL alone is insufficient

## P1 — Customer channel and core knowledge

- [ ] S1 Public customer webhook
  - [x] Audit: HTTPS webhook returns 404
  - [ ] Compare local route, Nginx routing, DNS and TLS to isolate cause
  - [ ] Correct routing; wrong verification token returns expected rejection
  - [ ] Verify Meta subscription and signed test event
  - [ ] Test inbound → approval → outbound with authorized test customer
- [ ] S2 Business knowledge and sales readiness
  - [x] Audit: 19 Markdown files, 15 contain TODOs; pricing unfinished
  - [ ] Sakir supplies approved product facts, prices, company details and FAQ answers
  - [ ] Replace placeholders; review and reindex
  - [ ] Multilingual sample set and customer safety tests pass
  - [ ] Verify opt-out, delivery windows and human handoff
  - [ ] Collect two weeks of reviewed drafts before considering narrow autonomy
  - [x] Audit baseline: leads/messages/approvals/calendar all zero; metrics records = 2

## P1 — Speech and knowledge retrieval

- [ ] V1 Healthy speech service
  - [x] Audit: Bangla model conversion to CTranslate2 failed; STT unhealthy
  - [ ] Reproduce conversion error and inspect dependency/model compatibility
  - [ ] Fix and build tested image
  - [ ] Deploy and verify healthy service
  - [ ] Test 10 Bangla and 10 English samples; at least 18 correctly understood
  - [ ] Verify embeddings and knowledge retrieval (shared STT dependency)

## P2 — Deployment and daily workflows

- [ ] D0 Reproducible core source and deployment
  - [x] Commit backup fix, core source and nested tracker on fix/recovery-and-progress
  - [x] Add read-only deployment audit that reports paths/status without secrets
  - [ ] Compare live core files against committed revision
  - [ ] Capture any live-only reusable scripts after secret review
  - [ ] Document fresh-server deployment and generated host configuration
  - [ ] Merge changes to main after validation


- [ ] D1 Reconcile server source and deployed bundle
  - [x] Root source checkout observed at 23137fc; current main at audit was 451a8b3
  - [x] Live settings-ui code/service absent; all 13 existing containers running
  - [ ] Establish admin-owned source checkout and record deployed revisions
  - [ ] Review changes before deploying; preserve live configuration and secrets
  - [ ] Deploy dashboard/settings only after recovery is proven
- [ ] D2 Prove useful scheduled work
  - [x] Audit n8n runtime: zero workflows
  - [ ] Verify Hermes schedules through supported runtime interface
  - [ ] Seven days of morning/evening briefs with useful factual data
  - [ ] Approved content pack and one verified Facebook/Instagram delivery
  - [ ] Monitoring detects controlled test failure and notifies owner

## P3 — Expanded vision (planned, not operational)

Each item must pass its detailed gate in [CAPABILITIES.md](CAPABILITIES.md).
Follow dependencies in [DELIVERY.md](DELIVERY.md); do not activate paid services
or external publishing merely by checking a documentation task.

- [ ] Marketing and production content
  - [ ] C04 Campaign strategy and measurable campaign pilot
  - [ ] C05 SEO audit, reviewed changes and measurement
  - [ ] C06 Sourced lead discovery with consent/suppression controls
  - [ ] C07 Finished graphics and Bangla/English product books
  - [ ] C08 Rendered video/reels with approved assets and cost limits
  - [ ] C09 Additional social integrations and delivery reconciliation
- [ ] Customer/business integrations
  - [ ] C10 WhatsApp and website customer adapters
  - [ ] C11 External CRM and availability-checked demo booking
  - [ ] C12 Support ticket ownership and escalation
  - [ ] C14 Reconciled cross-platform reporting
  - [ ] C13 Advertising dry run, approved cap and emergency stop
- [ ] Autonomous work and personal assistance
  - [ ] C01 Durable multi-role coordination, restart and cancellation
  - [ ] C02 Isolated issue-to-PR development across two projects
  - [ ] C03 Native production provisioning and staged deployment
  - [ ] C15 Reviewed memory, deletion and regression evaluation
  - [ ] C16 Personal email/calendar access and factual career drafts
  - [ ] C17 Versioned business workflows with bounded retries and stop procedures
  - [ ] C18 Private live voice/video pilot with consent and measured cost/latency

## Evidence log

| Date (Dhaka) | Item | Evidence | Remaining gate |
| --- | --- | --- | --- |
| 2026-10-31 | Audit | Termius health, database counts and redacted service logs | No new business workflow acceptance established |
| 2026-10-31 | R1 local tests | `python3 -m unittest discover -s tests -v`: 6 passed | Live deployment, backup, remote copy and restore |

| 2026-10-31 02:35 | R1 live backup | `Backup finished`; 167 MB encrypted local archive after targeted deployment of 5321a12 | Off-site destination missing; restore and SQLite consistency remain open |
