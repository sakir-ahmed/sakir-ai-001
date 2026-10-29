# Sakir AI 001 — rules for every AI tool

This file is the single source of rules for any AI coding tool that works on
this repo or on Sakir's server: Claude Code, OpenAI Codex, Grok Build, Gemini CLI,
Cursor or anything else. `CLAUDE.md` and `GEMINI.md` only point here.

## Who you are working for
- **Owner:** Sakir Ahmed — Lead Software Engineer, founder of Datatech BD Ltd. (Dhaka).
- **System name:** **Sakir AI 001**. When you introduce yourself on this server or in this
  repo, say you are working as part of Sakir AI 001.
- **Language:** reply in the language Sakir uses (Bangla, Banglish or English). Code, comments
  and docs are in English.
- **Timezone:** Asia/Dhaka.

## What this repo is
An installer bundle. `sudo bash install.sh` copies it to `/opt/sakir-ai` on Ubuntu 22.04/24.04
and runs everything in Docker. Read these before changing anything:
1. `docs/ARCHITECTURE.md` — the system as built (source of truth)
2. `docs/DECISIONS.md` — why it is built this way; add an entry for any behaviour change
3. `docs/OPERATIONS.md` — how it is run, updated and restored
4. `Sakir AI 001 — Build Blueprint.md` — the original plan; do not edit it to match the code

## Layout
| Path | What |
| --- | --- |
| `install.sh`, `lib/common.sh` | Idempotent installer; each `step_*` function is one step |
| `compose.yml`, `versions.env` | All services; image tags are copied into `/opt/sakir-ai/.env` |
| `services/dt-assistant/` | Sales pipeline (FastAPI, asyncpg). Pure rules in `app/policy.py` |
| `services/safe-exec/`, `hostops/`, `config/allowlist.yaml` | The only path from Sakir AI agents to the server |
| `services/stt`, `tts`, `indexer` | Speech and knowledge search |
| `hermes/skills/*/SKILL.md` | Hermes skills (frontmatter `name` must equal the folder name) |
| `tools/sakir.py` | CLI used by the skills; standard library only |
| `scripts/` | `sakir-ai.sh` (daily ops), backups, restore test, health check, AI tool installer |
| `knowledge-templates/` | Starting knowledge; the live copy is `/opt/sakir-ai/knowledge` (not in Git) |
| `docs/` | Architecture, decisions, operations, roadmap, AI tools |

## Hard rules (repo and server)
1. **Never print, copy, commit or send secrets.** That includes `/opt/sakir-ai/.env`,
   `/opt/sakir-ai/secrets/`, `/opt/sakir-ai/data/hermes/.env`, API keys, tokens and passwords.
   To check a secret is set, test that it is non-empty; never echo its value.
2. **Ask Sakir first, in the chat, and wait for a clear "yes"** before: reboot, shutdown,
   deleting files or folders, dropping or truncating database tables, `docker volume rm`,
   `docker system prune`, removing containers, firewall or SSH changes, and anything you cannot undo.
3. **Back up before risky changes:** run `sakir-ai backup` first.
4. **Use the project's tools, not raw commands, where they exist:** `sakir-ai status | health |
   logs | restart | update | reindex | backup` and `install.sh --step <name>`.
5. **Do not give Sakir AI agents a host shell.** New server abilities for Hermes = an entry in
   `config/allowlist.yaml` plus a branch in `services/safe-exec/app.py`
   (and in `hostops/sakir-hostops` for host actions).
6. **Customer safety:** `price`, `discount`, `order`, `complaint`, `legal`, `other` must stay in
   `never_auto` (`config/dt-assistant.yaml`). Customers talk to "Datatech BD Assistant"; it never
   claims to be human.
7. **No Grameenphone or eGeneration internal information** in any file, prompt or output.
8. **Never push to `main` without Sakir asking.** Work on a branch; commit messages explain why.
9. **Comment for a single maintainer:** every file starts with what it does and why; explain
   non-obvious lines.

## Working on the server
- Log in as the admin user `sakir` (not root); use `sudo` only for the command that needs it.
- The live install is `/opt/sakir-ai`; the Git clone (for example `~/sakir-ai-001`) is the source.
  Change code in the clone, commit, then deploy with
  `sudo bash install.sh --step layout && sudo bash install.sh --step stack`.
- Edit live settings only in `/opt/sakir-ai/config/` and `/opt/sakir-ai/knowledge/`, then
  restart the affected service (`sakir-ai restart <service>`) or `sakir-ai reindex`.
- After any change: `sakir-ai health` must show no FAIL.

## Checks before committing
```bash
bash -n install.sh lib/common.sh scripts/*.sh hostops/sakir-hostops
shellcheck -x -S warning install.sh lib/common.sh scripts/*.sh hostops/sakir-hostops
python3 -m py_compile $(git ls-files '*.py')
docker compose config --quiet        # needs secrets/*.env stubs and a .env
cd services/dt-assistant && pip install -r requirements-dev.txt && \
  TEST_DATABASE_URL=postgresql://user@127.0.0.1:5432/sakirai_test pytest
```
