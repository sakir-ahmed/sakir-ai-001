# Working outcomes — definition of complete

This document keeps the final Sakir AI 001 goal separate from tool installation.
The goal is a useful personal, development and business assistant with bounded
execution, measurable results and owner control. No outcome is complete merely
because a container, tool, prompt or skill exists.

## Completion rule

For each outcome: implement → test with isolated inputs → deploy → verify through
its real entry point → record the result → repeat over the agreed observation
period. All steps are necessary. Evidence must include date, environment, source
revision, expected/actual result, external delivery receipt where relevant, and
open limitations. Failed or missing evidence keeps the outcome unchecked.

[PROGRESS.md](PROGRESS.md) is the nested execution checklist. [CAPABILITIES.md](CAPABILITIES.md)
contains detailed C01–C18 acceptance gates. This table connects them to the work
Sakir actually wants done.

| Outcome | Demonstration required | Current evidence / gap | Tracking |
| --- | --- | --- | --- |
| Customers receive safe, useful help | Real authorized Meta test message → correct knowledge → draft → owner approval → delivered reply; never-auto intents remain gated | Local HTTP route works; public Cloudflare HTTPS route returns 404; no verified customer round trip | S1/S2; C10–C12 |
| Approved marketing becomes published content | Product facts → complete reviewed content pack → approved calendar → verified post/media receipt → measured result | Draft instructions and publisher foundation; no posts in audited calendar | D2; C04–C09 |
| Projects move from issue to reviewed delivery | Scoped issue → isolated project work → tests → reviewed PR → separately approved staging/production deployment | Coding tool installation is not this workflow | C01–C03 |
| Personal assistance saves daily time | Source-backed morning/evening briefs, factual career/learning output and approved calendar actions | Skills exist; seven-day useful-delivery evidence missing | D2; C16 |
| Operations detect and recover from failure | Actionable alert → bounded diagnosis/remediation → owner approval where required → verified service recovery; restore drill | Local backup now finishes; STT and alert/restore gaps remain | R1/R3/V1; C03/C17 |
| Business decisions use reliable numbers | Reconciled sales/content/spend report with freshness, source and attribution limits | Local metrics foundation; cross-platform/revenue reconciliation missing | C14 |
| Voice and memory work accurately | Bangla/English voice test → response; reviewed fact correction changes retrieval without changing policy | STT model failed; knowledge placeholders remain; live calls planned | V1/S2; C15/C18 |

Paid advertising, outbound discovery and new customer channels each require their
own acceptance tests and approved account scope. No unapproved outreach or spending
is implied by the overall goal. Missing approved product facts are requested from
Sakir, never invented.

## Customer-route findings — 2026-10-31

Read-only checks through Termius:

- Application `127.0.0.1:8081`: invalid verification token → expected HTTP 403.
- Host Nginx with `Host: ai.datatechbd.com`: same probe → expected HTTP 403.
- Public `https://ai.datatechbd.com`: same probe → unexpected HTTP 404.
- Origin HTTPS with correct server name: certificate hostname mismatch; Sakir AI
  Nginx site currently has port 80 listeners, not its own HTTPS listener.
- Nginx configuration syntax passes. These checks isolate the problem to the public
  proxy/origin/HTTPS path, but do not identify the actual Cloudflare origin target.

**Owner choice:** use the new `ai001.sakir.bd` A record and retain Cloudflare proxy.
The preceding findings describe the old hostname, not the new hostname acceptance. Do not switch the record to direct
DNS. Determine whether this hostname uses a proxied DNS record or Cloudflare Tunnel;
inspect that route and its upstream before changing it. A Cloudflare Tunnel may
use the local HTTP service behind an authenticated outbound tunnel; a proxied DNS
origin needs an appropriate authenticated HTTPS/TLS setup. Do not disable certificate
validation or weaken Cloudflare TLS mode to hide the failure.

Repeat the public probe locally with Postman after routing changes:

```bash
postman request 'https://ai001.sakir.bd/meta/webhook?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=1' \
  --no-report-events --timeout 15000 \
  --script-post-request @tests/postman/webhook-route.js
```

This must pass both assertions. It proves routing and invalid-token rejection,
not successful subscription, model quality, human approval or customer delivery.
Those remain separate unchecked acceptance tasks. No real customer event was
submitted or forwarded to a new hosted capture service during these diagnostics.
