# AI costs and free-first routing

This policy reduces routine model spend without making customer safety depend on
model price. It does not make the server, external tools, advertising or every API
free. Installation/configuration is distinct from verified live rollout.

## Sales routing

| Work | First attempt | On eligible failure |
| --- | --- | --- |
| Classification, routine reply, follow-up | `openrouter/free` | Gemini 2.5 Flash-Lite, if paid is enabled and budget allows |
| Existing complex/escalation draft (`reply_premium`: complaints/proposal-stage leads) | DeepSeek V3.2 | Free router |

The free router automatically chooses a currently available model supporting the
request features. It is not a fixed-quality model. All existing money/complaint/
legal/customer approval gates remain unchanged; multilingual quality evaluation
is still required before increasing autonomy.

- At most two attempts per call by default; hard implementation maximum four.
- Free HTTP 429 triggers a shared in-process cooldown of at least 60 seconds,
  honoring a numeric Retry-After up to 24 hours. It does not hammer other free
  variants against a shared daily limit. Cooldown resets on process restart.
- Eligible HTTP fallback statuses: 404, 408, 429, 500, 502, 503, 504, 524, 529.
  Auth, billing, invalid-request and moderation errors do not trigger paid retry.
- Empty or malformed JSON output may use the next configured model. Successful
  responses are cost-accounted before retry, including unusable output.
- Each request has price ceilings, 500 maximum output tokens and 24,000 maximum
  input bytes. Oversized input is refused rather than silently truncating policy.
- Providers are price-sorted and filtered with `data_collection: deny`. Free
  availability may be lower under this restriction; privacy is not relaxed to
  obtain a free response. No prompt logging or provider-registration changes occur.
- At the monthly paid cap, paid calls stop while free inference remains eligible.
  Paid calls reserve a conservative token-cost allowance before sending. A lock
  serializes budget checks/calls/accounting inside this service process.
- Actual returned cost is recorded. Missing cost uses configured price ceilings;
  entirely missing usage uses the paid request's conservative reservation estimate.
  Logs contain model/purpose/cost, not prompts or raw provider error bodies.

## Prices and spending boundaries

OpenRouter catalog checked 2026-10-31 (USD per million tokens):

| Model | Input | Output |
| --- | ---: | ---: |
| Free router | 0 | 0 |
| Gemini 2.5 Flash-Lite | 0.10 | 0.40 |
| DeepSeek V3.2 | 0.26 | 0.38 |

These are configured request price ceilings, not promises of permanent provider
pricing. A price increase may make the route unavailable rather than silently
increase its permitted price. No purchases or credit top-ups were made.

The app's existing $26 monthly sales ceiling is preserved, not a spending target.
The live sales key reported a $10 provider-side limit during this audit, with
almost all of it remaining; no reset period was inferred. Provider limits can
change and are the hard boundary across services, ambiguous timeouts and missing
usage. A database lock in one process is not an account-wide budget guarantee.
Hermes spend is not included in dt-assistant's spend table. Use separate capped
keys and the OpenRouter dashboard for total account/agent spend.

Free variants currently have published limits of 20 requests/minute, generally
50/day, or 1,000/day for qualifying purchased-credit accounts. Failed attempts
count. Classification plus drafting can use two requests per customer turn;
600 turns/day can exceed 1,000 requests even before Hermes/background work.
Changing free models, adding keys or creating retry loops is not a daily-quota
workaround. If free and allowed paid routes fail, the existing holding/draft
workflow and human review take over.

## Easy free-only switch

After a backup, apply only the selected cost settings while preserving autonomy,
existing budgets, custom settings and credentials:

```bash
sudo python3 scripts/apply-model-policy.py --source "$PWD" --sales-only --free-only
sakir-ai restart dt-assistant
```

For free-first with limited paid fallback, omit `--free-only`. These commands
assume the new sales code/image is already deployed. Initial code rollout needs
an image rebuild and owner-approved container recreation. Never use a config-only
restart as proof that new image code was activated.

## Hermes

`config/hermes-model-policy.yaml` contains reusable OpenRouter free-first defaults,
low-cost fallback and free auxiliary models. New installer setups use it. The
installed Hermes version was checked for legacy `fallback_model` support.

The audited live configuration pointed a `:free` model ID at Nous with no fallback.
A subsequent key check found no OpenRouter key available after loading its mounted
.env. Do not switch that live assistant until Sakir privately provisions a dedicated
OpenRouter key with a hard cap. Never send a key in chat or commit it to Git.

Once credentials are provisioned and compatibility checked, omit `--sales-only`
to merge both policies and restart Hermes. Existing sessions can retain their
creation-time route; use `/model openrouter:openrouter/free` in the private bot for
an existing chat, then verify the active model. Complex work can select a reviewed
stronger model explicitly; automatic semantic complexity routing for Hermes is
not implemented by this sales change. Native retries/auxiliary billing remain
Hermes-version-dependent and need separate live verification.

## Evidence and recheck

- 45 local sales tests passed against an isolated Postgres before the final policy
  merge helper additions; includes budget, failover and unchanged approvals.
- Additional prompt-size and policy-merge tests added and passed separately.
- One live synthetic free-only probe, with data-collection denied and zero price
  ceilings, returned nonempty content and reported cost 0. It sent no customer data.
- Paid fallback and quota failures were exercised with fake HTTP, not live paid
  requests; no claim of measured monthly savings or multilingual production quality.

A safe account-limit check and optional free-only probe is committed as
`scripts/check-model-routing.py`; run inside a service with its existing key.
The optional `--smoke` consumes one free request and never adds a paid fallback.

## Primary sources

- [Free router](https://openrouter.ai/openrouter/free)
- [Rate and credit limits](https://openrouter.ai/docs/api_reference/limits)
- [Model fallbacks and billing](https://openrouter.ai/docs/guides/routing/model-fallbacks)
- [Provider price ceilings and data policies](https://openrouter.ai/docs/guides/routing/provider-selection)
- [Live model catalog](https://openrouter.ai/api/v1/models)
- [Hermes fallback configuration](https://hermes-agent.nousresearch.com/docs/user-guide/features/fallback-providers)

Orbit discovered the OpenRouter chat-completions contract; its integration brief
request returned 403. Official provider documentation/catalog supplied the verified
routing, pricing and limit details. Firecrawl developer search returned 402, so
research continued with official sources.
