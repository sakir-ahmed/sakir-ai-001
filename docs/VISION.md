# Sakir AI 001 — complete capability plan

This document records the personal, business, development and operations vision and
its delivery requirements. It extends the original blueprint without rewriting it.
It is a plan, not a claim that the workforce is already operational.

## Reading order and authority

- [ARCHITECTURE.md](ARCHITECTURE.md): what the repository implements.
- [DECISIONS.md](DECISIONS.md): accepted constraints; these still apply here.
- [CAPABILITIES.md](CAPABILITIES.md): evidence, gaps and acceptance criteria by capability.
- [DELIVERY.md](DELIVERY.md): proposed integrations, controls and phased rollout.
- [ROADMAP.md](ROADMAP.md): dated installation evidence and delivery checklists.
- [OPERATIONS.md](OPERATIONS.md): current operational procedures.

## Outcome

Sakir AI 001 should help Sakir run Datatech BD, develop multiple products, manage
marketing and sales, support customers, and maintain personal priorities through
one private assistant. Customers continue to interact with “Datatech BD Assistant”.
Bangla, Banglish and English are required throughout. Scheduled work should produce
reviewable results and useful alerts, with a clear owner for every outstanding task.

The scope includes specialized agent roles for development, DevOps, research,
marketing, content, sales, support and personal assistance. Today Hermes skills
provide role instructions; they are not evidence of independent workers, durable
cross-agent orchestration or an autonomous development platform.

## Existing decisions that constrain every phase

1. AI services stay in Docker; future DT production applications run natively with
   isolated users/databases and resource priority (D-013 supersedes D-007's older
   production-container suggestion). No native production installer exists yet.
2. Agent server actions go through named safe-exec actions. No arbitrary host shell.
   Risky actions require Sakir's explicit approval and the existing confirmation flow.
3. Money, orders, complaints, legal and `other` customer intents remain in
   `never_auto`; no new integration may bypass the policy or approval desk.
4. The core sales pipeline stays in tested Python, not a replacement n8n workflow.
   n8n is available for separate owner workflows, not evidence those workflows exist.
5. Facebook/Instagram publishing has code; other social platforms use reminders
   until a separate reviewed integration is implemented (D-010).
6. Hermes and the sales approval desk use separate Telegram bots (D-008).
7. Settings UI is privileged owner administration, never an agent tool (D-015).
8. Secrets remain outside Git, prompts, knowledge and reports. No Grameenphone or
   eGeneration internal information may enter any artifact or model input.

## Success and limits

The blueprint's under-$100 monthly goal is a historical planning target, not a
verified current bill or a budget for every new capability. Measure baseline spend
before adding image/video generation, paid advertising, external connectors or
live calls. Advertising spend must have its own explicit authorization and cap.

Record monthly: Sakir's review time, first reply time, draft edit rate, qualified
leads, demos, approved posts delivered, incidents detected, restore success and
actual spend. Establish baselines first; do not claim improvement without data.
The blueprint's dates and numerical targets remain historical goals. New phases
are evidence-gated rather than promises tied to those dates.

## What complete documentation means

Each capability below has a current evidence statement, a proposed workflow,
integration dependencies, safety boundaries and a measurable acceptance gate.
Completing this documentation does not complete the software. Provider choice,
account permissions, costs and production activation remain separate delivery work.
