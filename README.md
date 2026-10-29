# Sakir AI 001 — installer bundle

Everything needed to turn a fresh Ubuntu 22.04/24.04 server into Sakir AI 001:
Hermes Agent on Telegram, the Datatech BD sales assistant for Facebook and
Instagram, speech in Bangla and English, knowledge search, safe server
actions with approval codes, monitoring and encrypted backups — all in Docker.

```
sudo bash install.sh
```

The installer is idempotent: re-run it any time, or run one step with
`--step <name>`. Every step is explained at the top of `install.sh`.

| Document | What it covers |
| --- | --- |
| [Build Blueprint](Sakir%20AI%20001%20%E2%80%94%20Build%20Blueprint.md) | The original master plan: goals, agents, budget, risks, success measures |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | The system as built, with diagrams |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Why things are the way they are (and where they differ from the blueprint) |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Daily/weekly/monthly routines, incident playbooks, updates, full restore |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phases and a checklist to tick off as you go |
| [docs/AI-TOOLS.md](docs/AI-TOOLS.md) | Claude Code, Codex, Grok Build and Gemini CLI on the server |
| [AGENTS.md](AGENTS.md) | Rules every AI tool follows on this repo and server |

---

## 1. Before you install (about 1 hour, mostly waiting)

Collect these first. You can install without some of them and add them later
with `sudo bash /opt/sakir-ai/install.sh --step secrets`.

| # | What | How | Needed for |
| --- | --- | --- | --- |
| 1 | **SSH key** on your laptop | `ssh-keygen -t ed25519`, then `ssh-copy-id root@<server-ip>` | Safe login; password login is turned off once a key works |
| 2 | **Domain for webhooks** | DNS A record, e.g. `ai.datatechbd.com` → server IP | HTTPS for Facebook webhooks |
| 3 | **Your Telegram user ID** | message @userinfobot | Only you can use the bots |
| 4 | **@SakirAI_bot** token | @BotFather → `/newbot`, display name **Sakir AI 001** | Hermes (your assistant, "Sakir AI 001") |
| 5 | **@DTSalesDesk_bot** token | @BotFather → `/newbot` | Approving customer replies |
| 6 | **OpenRouter** account, $40 credit, 2 keys | openrouter.ai → Keys: `hermes-core` (limit $12), `sales` (limit $26) | AI models |
| 7 | **Meta app** | developers.facebook.com → Business app → add Messenger + Webhooks; business verification of Datatech BD Ltd. | Facebook/Instagram replies and posting |
| 8 | Meta **App Secret**, **Page ID**, long-lived **Page token** | App settings → Basic; Graph API Explorer | same |
| 9 | Instagram business account ID (optional) | Linked to the Facebook Page | Instagram DMs and posts |

Meta permissions to request: `pages_messaging`, `pages_read_engagement`,
`pages_manage_metadata`, `pages_read_user_content`, `pages_manage_engagement`,
`pages_manage_posts`; for Instagram also `instagram_basic`,
`instagram_manage_messages`, `instagram_content_publish`. App review can take
1–3 weeks — start it on day 1. Until then the app works for page admins/testers.

---

## 2. Install

```bash
# from your laptop
scp sakir-ai-installer.zip root@<server-ip>:/root/
ssh root@<server-ip>

# on the server
apt-get update && apt-get install -y unzip
unzip sakir-ai-installer.zip && cd sakir-ai
sudo bash install.sh
```

It asks for the values above (secrets are typed hidden), shows the Hermes setup
wizard, and prints the backup private key **once** — save it in your password
manager. Total time: 20–40 minutes, most of it downloading images and speech
models.

When the Hermes wizard asks:
- Provider: **OpenRouter** → paste the `hermes-core` key
- Model: **deepseek/deepseek-v3.2** (good and cheap); fallback `google/gemini-2.5-flash`
- Messaging: **Telegram** → bot token and your user ID are pre-filled; confirm them

### Useful flags
```bash
sudo bash install.sh --list              # which steps are done
sudo bash install.sh --step tls          # get HTTPS after DNS points here
sudo bash install.sh --step secrets      # add or change tokens later
sudo bash install.sh --from stack        # rebuild/restart from the stack step
sudo bash install.sh --step aitools      # add Claude Code / Codex / Grok / Gemini CLI later
```

---

## 3. After install — checklist

1. **Test SSH in a new terminal** as `sakir` before closing the root session.
2. `sakir-ai health` → everything PASS (stt may say "starting" for ~10 minutes).
3. **HTTPS**: if the tls step was skipped, point DNS, then `sudo bash /opt/sakir-ai/install.sh --step tls`.
4. **Meta webhook** (App → Webhooks → Page):
   - Callback URL: `https://<your-domain>/meta/webhook`
   - Verify token: `sakir-ai secret META_VERIFY_TOKEN`
   - Subscribe fields: `messages`, `messaging_postbacks`, `feed`
   - Then subscribe the Page to the app (Messenger settings → Webhooks → Add subscriptions).
5. **Knowledge**: fill the TODOs in `/opt/sakir-ai/knowledge/`, first
   `products/dt-restora/pricing.md`, `features.md`, `faq.md` and `me/voice.md`,
   then `datatech/brand.md`, `datatech/case-studies.md` and `sales/objections.md`.
   Then `sakir-ai reindex`.
   Optional: push it to a private GitHub repo to edit from your phone:
   `cd /opt/sakir-ai/knowledge && git remote add origin git@github.com:<you>/sakir-knowledge.git && git push -u origin main`
6. **Off-server backups**: `sudo rclone config` → create a remote named
   `sakir-backup` (Backblaze B2 or S3). Then `sakir-ai backup` and check it uploaded.
7. **Hermes schedules** — send @SakirAI_bot:
   - "Every day at 08:30 run the daily-brief skill (morning)."
   - "Every day at 21:30 run the daily-brief skill (evening)."
   - "Every Monday at 10:00 run career-scout."
   - "Every Tuesday and Friday at 11:00 run linkedin-writer."
   - "Every Sunday at 09:00 run learning-coach."
8. **Uptime Kuma** (`https://<tailnet-name>:3444` or SSH tunnel): create the admin
   account, add a Telegram notification (@SakirAI_bot token + your ID), and add
   monitors: each DT site, `https://<domain>/meta/webhook` (keyword: none; expect 403
   is fine), certificate expiry.
9. **Grafana** (`https://<tailnet-name>:3443`): log in as `admin` with
   `sakir-ai secret GF_SECURITY_ADMIN_PASSWORD`; Loki is already connected.
10. **Test the sales flow**: from a personal Facebook account (added as a tester),
    message the Page "dam koto?" → a draft card appears in @DTSalesDesk_bot within a
    minute → tap Approve → the reply arrives in Messenger.
11. **Test approvals**: tell @SakirAI_bot "reboot the server" → it explains → you agree
    → a code arrives → send `confirm <id> <code>` (only after a backup exists).

No Tailscale? Use an SSH tunnel from your laptop:
`ssh -L 5678:127.0.0.1:5678 -L 3000:127.0.0.1:3000 -L 3001:127.0.0.1:3001 sakir@<server-ip>`
then open http://localhost:5678 (n8n), :3000 (Grafana), :3001 (Uptime Kuma).

---

## 4. Daily use

### Telegram
| Bot | You use it for |
| --- | --- |
| **@SakirAI_bot** (Hermes) | briefs, questions, voice notes, content packs, jobs, LinkedIn, server checks, `confirm <id> <code>` |
| **@DTSalesDesk_bot** | Approve / Edit / Reject customer replies; `/inbox`, `/stats`, `/lead`, `/pause`, `/resume` |

### Server command
```
sakir-ai status            containers and resource use
sakir-ai health            full check
sakir-ai logs dt-assistant -f
sakir-ai restart hermes
sakir-ai reindex           after editing knowledge files
sakir-ai backup            backup now
sakir-ai update            backup, pull new images, rebuild, restart
sakir-ai pause | resume    stop/start automatic customer replies
sakir-ai secret KEY        show one secret value
sakir-ai versions          image versions (pin them in /opt/sakir-ai/.env)
```

### Turning up autonomy (after 2 clean weeks)
Edit `/opt/sakir-ai/config/dt-assistant.yaml`:
```yaml
autonomy:
  auto_intents: [faq, demo]     # never add price, discount, complaint, order, legal
  auto_send_templates: true
```
then `sakir-ai restart dt-assistant`.

---

## 5. What is where

```
/opt/sakir-ai/
├── install.sh, lib/          installer (re-runnable)
├── compose.yml, versions.env all containers; image tags (copied into .env)
├── .env                      domain, timezone, image tags      (root, 600)
├── secrets/*.env             tokens and passwords              (root, 600)
├── config/                   allowlist.yaml, dt-assistant.yaml, nginx, loki, alloy, grafana
├── services/                 our code: dt-assistant, safe-exec, stt, tts, indexer
├── tools/sakir.py            the command Hermes skills use
├── hermes/skills/            10 Sakir skills (copied into data/hermes/skills)
├── knowledge/                Git repo of Markdown facts (edit these!)
├── data/                     databases, Hermes memory, models, logs
├── outbox/                   files agents create (posts, CVs, PDFs); outbox/public is served for Instagram
├── backups/                  encrypted nightly backups (14 days)
├── hostops/                  job queue for allowlisted host actions
└── scripts/                  sakir-ai.sh, backup.sh, restore-test.sh, healthcheck.sh, backup.d/
```

| Service | What it does | Reached at |
| --- | --- | --- |
| hermes | your assistant, skills, memory | Telegram @SakirAI_bot |
| dt-assistant | sales replies, approvals bot, publisher, internal API | `https://<domain>/meta/webhook`; Telegram @DTSalesDesk_bot |
| ai-db | leads, messages, approvals, calendar, spend | internal |
| safe-exec | allowlisted server actions + approval codes | internal |
| stt / tts | Bangla/English speech, embeddings / voice replies | internal |
| qdrant + indexer | knowledge search | internal |
| n8n (+ n8n-db) | your own no-code workflows | 127.0.0.1:5678; public webhooks at `/hooks/<path>` |
| uptime-kuma, loki, alloy, grafana | monitoring | 127.0.0.1:3001 / 3000 |

---

## 6. Security model (short)

- Only ports 22, 80, 443 are open; admin UIs listen on 127.0.0.1 only.
- SSH: key-only, root login off (applied only once your key works).
- Agents never get a shell on the host. Hermes reaches the server only through
  safe-exec's named actions; risky ones need a code that goes only to your Telegram.
- Only safe-exec and the log shipper mount the Docker socket.
- Customer messages cannot trigger server actions: the sales pipeline has no such tools.
- Secrets are root-only files; backups are encrypted with a key that is not on the server.
- Rotate keys with `scripts/rotate-keys.md`.

## 7. Troubleshooting

| Symptom | Check |
| --- | --- |
| No draft cards appear | `sakir-ai logs dt-assistant`; webhook subscribed? `curl https://<domain>/meta/webhook` should give 403 |
| "bad signature" in logs | META_APP_SECRET wrong → `install.sh --step secrets` |
| Replies "outside 24-hour window" | normal Meta rule; call/WhatsApp the lead instead |
| stt unhealthy | first start downloads ~2 GB; `sakir-ai logs stt` |
| Hermes silent | `sakir-ai logs hermes`; Telegram user ID in `data/hermes/.env` (`TELEGRAM_ALLOWED_USERS`) |
| Disk filling | `sakir-ai status`, `ncdu /opt/sakir-ai/data` |
| Restore needed | on your laptop: `scripts/restore-test.sh <backup> <key>` shows the data; restore = fresh install + copy `data/` from `files.tgz` + load the SQL dumps |

## 8. Developer notes

dt-assistant tests (pure logic, webhook layer, and end-to-end pipeline against Postgres with all APIs mocked):
```bash
cd services/dt-assistant
pip install -r requirements-dev.txt
TEST_DATABASE_URL=postgresql://user@127.0.0.1:5432/sakirai_test pytest
```
