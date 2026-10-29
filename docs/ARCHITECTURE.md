# Architecture (as built)

This describes the system the code in this repo actually installs. The original
plan is in [`Sakir AI 001 — Build Blueprint.md`](../Sakir%20AI%20001%20%E2%80%94%20Build%20Blueprint.md);
where the two differ, this file is correct and [DECISIONS.md](DECISIONS.md) says why.

## At a glance

```mermaid
flowchart TB
    subgraph IN["Inputs"]
        S["Sakir<br/>Telegram text + voice<br/>@SakirAI_bot"]
        C["Customers<br/>Facebook comments, Messenger,<br/>Instagram DMs"]
        SD["Sakir approvals<br/>@DTSalesDesk_bot"]
    end

    subgraph EDGE["Host"]
        NG["Nginx :443<br/>/meta/webhook · /hooks/* · /public-media/*"]
        HR["sakir-hostops (root)<br/>nginx · certbot · reboot · poweroff"]
    end

    subgraph AI["Docker network: ai"]
        H["Hermes Agent<br/>10 skills, memory, schedules"]
        T["tools/sakir.py"]
        DT["dt-assistant<br/>sales pipeline · approval desk ·<br/>publisher · follow-ups"]
        DB[("ai-db<br/>leads · messages · approvals ·<br/>calendar · spend")]
        SE["safe-exec<br/>allowlist + approval codes<br/>(Docker API: restarts, logs)"]
        STT["stt<br/>Bangla/English speech · embeddings"]
        TTS["tts"]
        Q[("Qdrant<br/>knowledge search")]
        N8N["n8n (own workflows)"]
    end

    subgraph OPS["Docker network: ops"]
        MON["Uptime Kuma · Loki · Alloy · Grafana<br/>(reads all container logs)"]
    end

    OR["OpenRouter<br/>DeepSeek · Gemini"]
    META["Meta Graph API v25"]

    S --> H
    H --> T
    T --> SE
    T --> DT
    T --> STT
    T --> TTS
    T --> Q
    C --> META --> NG --> DT
    DT <--> SD
    DT --> DB
    DT --> STT
    DT --> Q
    DT --> OR
    DT --> META
    H --> OR
    SE --> HR
```

Sakir talks to Hermes. Customers talk to dt-assistant, and Sakir approves its
replies in a second bot. Neither of them can touch the server directly: every
server action is a named action in safe-exec.

## Components

| Component | Code | Role | Talks to |
| --- | --- | --- | --- |
| Hermes Agent | upstream image, skills in `hermes/skills/` | Sakir's private assistant: briefs, content, career, branding, learning, DevOps questions, voice notes | OpenRouter, `tools/sakir.py` |
| `tools/sakir.py` | `tools/sakir.py` | The single command every skill uses (server, sales, content, kb, voice) | safe-exec, dt-assistant, stt, tts, Qdrant |
| dt-assistant | `services/dt-assistant/` | Facebook/Instagram sales replies, approval bot, content publisher, follow-ups, daily metrics, internal API | Meta, OpenRouter, Telegram, ai-db, stt, Qdrant |
| ai-db | Postgres 16, schema in `services/dt-assistant/app/schema.sql` | Leads, messages, approvals, content calendar, spend, settings, metrics | — |
| safe-exec | `services/safe-exec/` | Allowlisted server actions; risky ones need a code sent to Sakir | Docker socket, host job queue, Telegram |
| sakir-hostops | `hostops/sakir-hostops` + `systemd/` | Root runner for host actions (Nginx, SSL, reboot, power off) | host |
| stt | `services/stt/` | Bangla (BanglaSpeech2Text) and English (faster-whisper) transcription; multilingual-e5 embeddings | — |
| tts | `services/tts/` | Spoken replies (Bangla/English) | Microsoft Edge voices |
| Qdrant + indexer | `services/indexer/` | Search over `knowledge/` (collections `restora`, `me`, `ops`) | stt |
| n8n | upstream image | Free for Sakir's own no-code automations; not used by the core | — |
| Monitoring | `config/loki.yaml`, `config/alloy.config`, Grafana provisioning | Logs (30 days), uptime, dashboards | Docker socket (read-only) |
| settings-ui | `services/settings-ui/` | Dashboard (`/`: flow diagram, container health, sales pipeline, spend, backup age) + web edit form (`/settings`: tokens, keys, budget, autonomy, retention; "Apply" recreates the affected container) | Docker socket (read/write), the whole project directory, dt-assistant's `/internal/*` API |

## Customer message flow

```mermaid
flowchart TD
    A["Webhook from Meta"] --> B{"Signature valid?"}
    B -- no --> X1["401, logged"]
    B -- yes --> C["Queue, reply 200 at once"]
    C --> D["Dedupe by Meta id · upsert lead · store message"]
    D --> E{"Voice note?"}
    E -- yes --> F["stt: transcribe"]
    E -- no --> G
    F --> G{"Paused or over budget?"}
    G -- yes --> H["Holding reply + card for Sakir"]
    G -- no --> I["Classify: intent, language, confidence<br/>(Gemini Flash-Lite)"]
    I --> J{"policy.decide()"}
    J -- spam --> K["Hide comment"]
    J -- complaint / discount / legal --> L["Holding reply + premium draft card"]
    J -- FAQ with template --> M["Template in customer's language"]
    J -- other --> N["Search knowledge · draft reply<br/>(DeepSeek V3.2)"]
    M --> O{"Auto-send allowed?"}
    N --> O
    O -- yes --> P["Send via Graph API<br/>(inside 24-hour window)"]
    O -- no --> Q["Card in @DTSalesDesk_bot:<br/>Approve · Edit · Reject"]
    Q -- approve / edit --> P
    Q -- reject --> R["Nothing sent"]
```

Rules that never change without editing code (`app/policy.py`):
- `price`, `discount`, `complaint`, `order`, `legal` and `other` are never sent automatically.
- A voice note that could not be transcribed is never answered automatically.
- Messenger/Instagram replies are only sent inside Meta's 24-hour window (5-minute margin).
- At most one holding reply per lead every 12 hours.
- A double tap on Approve sends once (the approval row is claimed atomically).

## Risky server action flow

```mermaid
sequenceDiagram
    participant Sakir
    participant Hermes
    participant SafeExec as safe-exec
    participant Runner as sakir-hostops (root)
    Sakir->>Hermes: "reboot the server"
    Hermes->>Sakir: explains why and asks
    Sakir->>Hermes: "yes"
    Hermes->>SafeExec: POST /run reboot (reason)
    SafeExec->>SafeExec: on allowlist? backup < 24h?
    SafeExec-->>Sakir: Telegram: request id + 4-digit code
    SafeExec-->>Hermes: waiting_approval (no code)
    Sakir->>Hermes: "confirm a1b2c3 4821"
    Hermes->>SafeExec: POST /confirm
    SafeExec->>Runner: job file {id, action}
    Runner->>Runner: action on its own fixed list → systemctl reboot
```

Hermes never sees the code, so a prompt injection cannot approve anything.
Three wrong codes or 10 minutes cancel the request; a safe-exec restart
cancels all pending requests.

## Networks and exposure

| Exposure | What |
| --- | --- |
| Internet (UFW) | 22 (SSH, key-only), 80/443 (Nginx) |
| Public paths | `/meta/webhook` → dt-assistant, `/hooks/*` → n8n webhooks, `/public-media/*` → images for Instagram |
| 127.0.0.1 only | dt-assistant 8081, n8n 5678, Grafana 3000, Uptime Kuma 3001, settings-ui 8090 (reach via Tailscale or SSH tunnel) |
| Docker socket | safe-exec (read/write, allowlisted actions only), Alloy (read-only, logs), settings-ui (read/write, password-protected — see D-015) |
| DT products (future) | run natively on the host (Nginx → PHP-FPM/Node, MySQL/PostgreSQL, Redis via systemd), not in Docker — see D-013 |

## Resource limits

| Service | CPU | RAM |
| --- | --- | --- |
| hermes | 1.5 | 3 GB |
| dt-assistant | 1 | 768 MB |
| ai-db | 1 | 2 GB |
| n8n + n8n-db | 1.5 | 3 GB |
| qdrant | 0.5 | 2 GB |
| stt | 2 | 5 GB |
| tts, safe-exec | 0.5 | 512 MB |
| monitoring (4 services) | 1.25 | 2.4 GB |
| **Total cap** | **~9.25** | **~19 GB** |

That leaves about 3 vCPU and 29 GB of the 12 vCPU / 48 GB server for DT products.

## Data

| Data | Where | Backed up |
| --- | --- | --- |
| Leads, messages, approvals, calendar, spend | `data/ai-db` | nightly SQL dump |
| n8n workflows and credentials | `data/n8n-db`, `data/n8n` | nightly SQL dump |
| Hermes memory, skills, sessions, config | `data/hermes` | nightly (files) |
| Knowledge (source of truth) | `knowledge/` (Git) | nightly (files) + your Git remote |
| Search index | `data/qdrant` | not needed (rebuilt by `sakir-ai reindex`) |
| Speech models | `data/models` | not needed (re-downloaded) |
| Secrets | `secrets/`, `.env` | nightly (inside the encrypted archive) |
| Generated files | `outbox/` | not backed up — copy what you keep |

## Schedules (Asia/Dhaka)

| Time | Job | Runs in |
| --- | --- | --- |
| every 1 min | uptime checks | Uptime Kuma |
| every 1 min | publish due posts | dt-assistant |
| every 10 min | stale-draft warnings | dt-assistant |
| every 30 min | follow-up drafts | dt-assistant |
| 02:30 | knowledge re-index | systemd `sakir-index.timer` |
| 03:00 | encrypted backup | systemd `sakir-backup.timer` |
| 08:30 / 21:30 | morning brief / evening summary | Hermes schedule (set after install) |
| every 5 min | heartbeat to the outside monitor (if configured) | systemd `sakir-heartbeat.timer` |
| daily | delete messages/drafts/dead leads past retention | dt-assistant |
| 21:00 | daily metrics snapshot | dt-assistant |
| Mon 10:00 | job scan | Hermes schedule |
| Tue, Fri 11:00 | LinkedIn drafts | Hermes schedule |
| Sun 09:00 | learning plan | Hermes schedule |
