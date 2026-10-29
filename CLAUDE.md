# Sakir AI 001 — notes for AI assistants working on this repo

Owner: Sakir Ahmed (Datatech BD Ltd.). This repo is an installer bundle: `install.sh`
copies it to `/opt/sakir-ai` on an Ubuntu server and runs everything in Docker.

## Read first
- `docs/ARCHITECTURE.md` — what exists and how it connects (source of truth for the as-built system)
- `docs/DECISIONS.md` — why; add an entry for any change in behaviour
- `Sakir AI 001 — Build Blueprint.md` — the original plan; do not edit it to match the code, record differences in DECISIONS.md

## Layout
| Path | What |
| --- | --- |
| `install.sh`, `lib/common.sh` | Idempotent installer; each `step_*` function is one step |
| `compose.yml`, `versions.env` | All services; image tags are copied into `/opt/sakir-ai/.env` |
| `services/dt-assistant/` | Sales pipeline (FastAPI, asyncpg). Pure rules in `app/policy.py` |
| `services/safe-exec/`, `hostops/`, `config/allowlist.yaml` | The only path from agents to the server |
| `services/stt`, `tts`, `indexer` | Speech and knowledge search |
| `hermes/skills/*/SKILL.md` | Hermes skills (frontmatter `name` must equal the folder name) |
| `tools/sakir.py` | CLI used by skills; standard library only |
| `knowledge-templates/` | Starting knowledge; the live copy is `/opt/sakir-ai/knowledge` (not in Git here) |
| `docs/` | Architecture, decisions, operations, roadmap |

## Hard rules
- Never commit secrets, `.env`, `secrets/`, `data/`, `backups/` or a filled-in `knowledge/` (see `.gitignore`).
- Agents must never get a host shell: new server abilities = an entry in `config/allowlist.yaml`
  plus a branch in `safe-exec/app.py` (and in `hostops/sakir-hostops` for host actions).
- `price`, `discount`, `order`, `complaint`, `legal`, `other` must stay in `never_auto`.
- Keep Grameenphone / eGeneration internal information out of every file.
- Comment code for a reader who maintains it alone: what and why, at the top of each file.

## Checks before committing
```bash
bash -n install.sh lib/common.sh scripts/*.sh hostops/sakir-hostops
shellcheck -x -S warning install.sh lib/common.sh scripts/*.sh hostops/sakir-hostops
python3 -m py_compile $(git ls-files '*.py')
docker compose config --quiet        # needs secrets/*.env stubs and a .env
cd services/dt-assistant && pip install -r requirements-dev.txt && \
  TEST_DATABASE_URL=postgresql://user@127.0.0.1:5432/sakirai_test pytest
```
