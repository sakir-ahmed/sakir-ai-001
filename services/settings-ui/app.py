# =============================================================================
# settings-ui — Sakir AI 001's own web dashboard ("/") and edit form
# ("/settings").
#
# Why this exists: the installer's interactive prompts (`install.sh --step
# secrets`) were the only way to change tokens/keys, Hermes' own setup
# wizard turned out to be fragile over SSH, and there was no single page
# showing the whole system at a glance — what talks to what, whether
# everything is actually running, and what is waiting for Sakir's
# attention (approvals, budget, backups). This container is both: a live
# overview and the edit form, one login, one private port.
#
# Scope, on purpose: only values that (a) live in a plain env file or in the
# three editable blocks of config/dt-assistant.yaml, and (b) take effect by
# recreating one container. Domain/TLS/nginx changes are NOT here: those need
# real system commands (certbot, nginx -t) this container has no business
# running; `docs/OPERATIONS.md` still covers those.
#
# Safety:
#   - One HTTP Basic login (password set once at install, changeable with
#     `sakir-ai settings-password`). Never exposed publicly — see compose.yml.
#   - Secret fields are never redisplayed (same "blank keeps the old value"
#     rule as the installer's own prompts). We only ever show whether a
#     secret is set, never its value.
#   - `autonomy.never_auto` is not a field here at all, and whatever is typed
#     into auto_intents is rejected server-side if it overlaps that fixed
#     list (config/dt-assistant.yaml HARD_NEVER_AUTO below) — the single
#     customer-safety rule (AGENTS.md #6) cannot be switched off from this
#     page, even by someone who guesses the password.
# =============================================================================
from __future__ import annotations

import html
import json
import os
import re
import secrets
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

BASE = Path(os.environ.get("INSTALL_DIR", "/opt/sakir-ai"))
ENVF = BASE / ".env"
S = BASE / "secrets"
DT_ENV = S / "dt-assistant.env"
SAFE_ENV = S / "safe-exec.env"
HERMES_ENV = BASE / "data" / "hermes" / ".env"
DT_YAML = BASE / "config" / "dt-assistant.yaml"

AUTH_FILE = S / "settings-ui.env"  # SETTINGS_UI_USER / SETTINGS_UI_PASSWORD

# Mirrors config/dt-assistant.yaml autonomy.never_auto. Hard-coded on purpose:
# this page must refuse to help enable auto-sending these even if the yaml
# file itself were ever edited by hand to remove them.
HARD_NEVER_AUTO = {"price", "discount", "order", "complaint", "legal", "other"}
AUTO_INTENT_CHOICES = ["faq", "demo", "support", "greeting"]  # INTENTS - never_auto - spam

app = FastAPI(title="Sakir AI 001 — Settings")


# ---- tiny env-file helpers (same KEY=VALUE format lib/common.sh uses) ------
def env_get(path: Path, key: str) -> str:
    if not path.exists():
        return ""
    value = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(key + "="):
            value = line[len(key) + 1 :]
    return value.strip().strip('"')


def env_set(path: Path, key: str, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [l for l in (path.read_text(encoding="utf-8").splitlines() if path.exists() else []) if not l.startswith(key + "=")]
    lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o600)


# ---- targeted YAML edits that keep every comment and the rest of the file -
def yaml_set_scalar(path: Path, section: str, key: str, new_value: str) -> None:
    """Replace the value of `section:\\n  key: <value>  # comment` in place.

    A full yaml.safe_load()+dump() round-trip would silently throw away every
    comment in dt-assistant.yaml, which is exactly the documentation the next
    person editing it by hand relies on — so this edits one line, textually,
    and leaves everything else byte-for-byte unchanged.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    in_section = False
    done = False
    for line in lines:
        if not done and re.match(rf"^{re.escape(section)}:\s*$", line):
            in_section = True
            out.append(line)
            continue
        if in_section and line and not line[0].isspace() and not line.startswith("#"):
            in_section = False  # a new top-level key ended the section
        if in_section and not done:
            m = re.match(rf"^(\s*){re.escape(key)}:\s*([^#]*?)\s*(#.*)?$", line)
            if m:
                indent, _old, comment = m.groups()
                out.append(f"{indent}{key}: {new_value}" + (f"  {comment}" if comment else ""))
                done = True
                continue
        out.append(line)
    if not done:
        raise ValueError(f"{section}.{key} not found in {path}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def yaml_get_scalar(path: Path, section: str, key: str) -> str:
    in_section = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if re.match(rf"^{re.escape(section)}:\s*$", line):
            in_section = True
            continue
        if in_section and line and not line[0].isspace() and not line.startswith("#"):
            break
        if in_section:
            m = re.match(rf"^\s*{re.escape(key)}:\s*([^#]*?)\s*(#.*)?$", line)
            if m:
                return m.group(1).strip()
    return ""


# ---- apply: recreate one container so it picks up the new env/config -----
ALLOWED_SERVICES = ("hermes", "dt-assistant", "safe-exec")


def apply(*services: str) -> str:
    bad = [s for s in services if s not in ALLOWED_SERVICES]
    if bad:
        raise ValueError(f"not allowed to restart: {bad}")
    # --force-recreate: a plain `docker compose up -d` does not reliably
    # reread env_file content for an already-created container; recreating it
    # does, which is the whole point of an "Apply" button.
    proc = subprocess.run(
        ["docker", "compose", "up", "-d", "--force-recreate", *services],
        cwd=BASE, capture_output=True, text=True, timeout=120,
    )
    out = (proc.stdout + proc.stderr).strip()
    return out or "(no output)"


# ---- dashboard data: container health + dt-assistant's own read-only API --
DT_URL = "http://dt-assistant:8080"


def container_status() -> list[dict[str, str]]:
    """`docker compose ps`, one row per service — what settings-ui itself
    would otherwise need a dozen separate docker SDK calls to show."""
    try:
        proc = subprocess.run(
            ["docker", "compose", "ps", "--all", "--format", "json"],
            cwd=BASE, capture_output=True, text=True, timeout=20,
        )
        rows = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
        return sorted(
            [{"name": r.get("Service", "?"), "state": r.get("State", "?"),
              "health": r.get("Health", "") or "-"} for r in rows],
            key=lambda r: r["name"],
        )
    except Exception as exc:  # the dashboard must still render if this fails
        return [{"name": "(docker compose ps failed)", "state": str(exc), "health": "-"}]


def dt_api(path: str) -> dict | list | None:
    """GET one of dt-assistant's own /internal/* endpoints (the same ones
    Hermes' skills already call through tools/sakir.py). Returns None on any
    failure — dt-assistant may be paused, mid-restart, or not built yet —
    so the rest of the dashboard still renders."""
    token = env_get(DT_ENV, "INTERNAL_API_TOKEN")
    if not token:
        return None
    req = urllib.request.Request(f"{DT_URL}{path}", headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def last_backup_age() -> str:
    backups = BASE / "backups"
    files = sorted(backups.glob("sakir-ai_*.tar.age"), key=lambda p: p.stat().st_mtime) if backups.is_dir() else []
    if not files:
        return "none yet"
    import datetime as _dt
    age = _dt.datetime.now().timestamp() - files[-1].stat().st_mtime
    hours = age / 3600
    return f"{hours:.0f}h ago" if hours < 48 else f"{hours / 24:.0f}d ago"


# ---- auth -------------------------------------------------------------------
def require_login(request: Request) -> HTMLResponse | None:
    user = env_get(AUTH_FILE, "SETTINGS_UI_USER") or "sakir"
    password = env_get(AUTH_FILE, "SETTINGS_UI_PASSWORD")
    auth = request.headers.get("authorization", "")
    ok = False
    if password and auth.startswith("Basic "):
        import base64
        try:
            given_user, given_pw = base64.b64decode(auth[6:]).decode("utf-8", "replace").split(":", 1)
            ok = secrets.compare_digest(given_user, user) and secrets.compare_digest(given_pw, password)
        except Exception:
            ok = False
    if not ok:
        return HTMLResponse(
            "Login required.", status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Sakir AI 001 settings"'},
        )
    return None


# ---- the page ---------------------------------------------------------------
def esc(value: str) -> str:
    return html.escape(value, quote=True)


STYLE = """
  body { font-family: system-ui, sans-serif; max-width: 920px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }
  h1 { font-size: 1.3rem; }
  h2 { font-size: 1rem; margin: 1.6rem 0 .6rem; }
  nav { margin-bottom: 1.2rem; }
  nav a { margin-right: 1.2rem; color: #2563eb; text-decoration: none; font-size: .95rem; }
  nav a.active { font-weight: 700; color: #1a1a1a; }
  fieldset { border: 1px solid #ddd; border-radius: 8px; margin-bottom: 1.2rem; padding: 1rem 1.2rem; }
  legend { font-weight: 600; padding: 0 .4rem; }
  label { display: block; margin: .6rem 0; font-size: .92rem; }
  label.row { display: inline-block; margin-right: 1.2rem; }
  input[type=text], input[type=number], input[type=password] {
    width: 100%; max-width: 420px; padding: .4rem .5rem; margin-top: .2rem;
    border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box;
  }
  .hint { color: #777; font-weight: 400; font-size: .85em; }
  .readonly { color: #555; background: #f6f6f6; padding: .6rem .8rem; border-radius: 6px; font-size: .9rem; }
  button { background: #2563eb; color: #fff; border: 0; padding: .55rem 1.1rem; border-radius: 6px; font-size: .95rem; cursor: pointer; }
  button.secondary { background: #555; margin-left: .5rem; }
  .msg { background: #ecfdf5; border: 1px solid #a7f3d0; padding: .6rem 1rem; border-radius: 6px; white-space: pre-wrap; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 1rem; font-size: .9rem; }
  th, td { text-align: left; padding: .35rem .6rem; border-bottom: 1px solid #eee; }
  .up { color: #15803d; font-weight: 600; } .down { color: #b91c1c; font-weight: 600; }
  .cards { display: flex; flex-wrap: wrap; gap: .8rem; margin-bottom: 1rem; }
  .card { background: #f6f6f6; border-radius: 8px; padding: .7rem 1rem; min-width: 140px; }
  .card .n { font-size: 1.5rem; font-weight: 700; display: block; }
  .card .l { font-size: .8rem; color: #555; }
  .mermaid { background: #fff; }
"""


def layout(active: str, body: str) -> str:
    def link(path: str, label: str) -> str:
        cls = ' class="active"' if path == active else ""
        return f'<a href="{path}"{cls}>{label}</a>'

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sakir AI 001</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.1/mermaid.min.js"></script>
<style>{STYLE}</style></head>
<body>
<h1>Sakir AI 001</h1>
<nav>{link("/", "Dashboard")}{link("/settings", "Settings")}</nav>
{body}
<script>if (window.mermaid) mermaid.initialize({{ startOnLoad: true, theme: "neutral" }});</script>
</body></html>"""


def render_dashboard(message: str = "") -> str:
    banner = f'<p class="msg">{esc(message)}</p>' if message else ""
    containers = container_status()
    rows = "\n".join(
        f'<tr><td>{esc(c["name"])}</td>'
        f'<td class="{"up" if c["state"] == "running" else "down"}">{esc(c["state"])}</td>'
        f'<td>{esc(c["health"])}</td></tr>'
        for c in containers
    )

    summary = dt_api("/internal/summary?days=1")
    spend = dt_api("/internal/spend")
    approvals = dt_api("/internal/approvals")

    def card(n, label) -> str:
        return f'<div class="card"><span class="n">{esc(str(n))}</span><span class="l">{esc(label)}</span></div>'

    if summary is None:
        cards = '<p class="hint">dt-assistant did not answer — it may be paused, restarting, or not configured yet.</p>'
    else:
        stages = summary.get("leads_by_stage", {})
        stage_order = ["new", "interested", "demo", "proposal", "won", "lost"]
        cards = '<div class="cards">' + "".join(
            card(stages.get(s, 0), s) for s in stage_order
        ) + card(summary.get("messages_in", 0), "messages in (24h)") \
          + card(summary.get("approvals_waiting", 0), "approvals waiting") \
          + card("paused" if summary.get("paused") else "live", "mode") \
          + "</div>"

    if spend is None:
        spend_html = ""
    else:
        pct = (spend["month_usd"] / spend["limit_usd"] * 100) if spend.get("limit_usd") else 0
        spend_html = (f'<p>Sales spend this month: <b>${spend["month_usd"]:.2f}</b> of '
                      f'${spend["limit_usd"]:.2f} ({pct:.0f}%)</p>')

    if not approvals:
        approvals_html = '<p class="hint">Nothing waiting.</p>'
    else:
        approvals_html = "<ul>" + "".join(
            f'<li>{esc(str(a.get("channel_user_id", "?")))} — {esc(str(a.get("intent", "?")))}'
            f' <span class="hint">({esc(str(a.get("created_at", "")))})</span></li>'
            for a in approvals[:10]
        ) + "</ul>"
        if len(approvals) > 10:
            approvals_html += f'<p class="hint">+{len(approvals) - 10} more — see @DTSalesDesk_bot</p>'

    diagram = """
<div class="mermaid">
flowchart LR
  Sakir((Sakir))
  subgraph Assistant
    Hermes[Hermes Agent]
    SafeExec[safe-exec]
    HostOps[sakir-hostops]
  end
  subgraph Sales
    Meta[Meta Graph API]
    DT[dt-assistant]
    AIDB[(ai-db)]
    Desk[DTSalesDesk bot]
  end
  Customer((FB/IG customer))

  Sakir -- Telegram --> Hermes
  Hermes -- skills --> SafeExec
  SafeExec -- approval code --> Sakir
  SafeExec -- host actions --> HostOps
  HostOps --> Server[(this server)]

  Customer -- comment/DM --> Meta
  Meta -- webhook --> DT
  DT <--> AIDB
  DT -- draft/escalate --> Desk
  Desk -- approve/reject --> Sakir
  Desk -- approved reply --> Meta

  You[/You are here: settings-ui\\n"dashboard" + "settings"/]
  You -.reads.-> DT
  You -.recreates.-> Hermes
  You -.recreates.-> DT
</div>"""

    return layout("/", f"""{banner}
<h2>System flow</h2>
{diagram}

<h2>Containers</h2>
<table><tr><th>Service</th><th>State</th><th>Health</th></tr>{rows}</table>

<h2>Sales pipeline (last 24h)</h2>
{cards}
{spend_html}

<h2>Approvals waiting for you</h2>
{approvals_html}

<h2>Backups</h2>
<p>Last encrypted backup: <b>{esc(last_backup_age())}</b></p>
""")


def render_settings(message: str = "") -> str:
    owner = env_get(DT_ENV, "TELEGRAM_OWNER_ID")
    hermes_bot_set = bool(env_get(SAFE_ENV, "TELEGRAM_BOT_TOKEN"))
    sales_bot_set = bool(env_get(DT_ENV, "SALES_BOT_TOKEN"))
    or_hermes_set = bool(env_get(HERMES_ENV, "OPENROUTER_API_KEY"))
    or_sales_set = bool(env_get(DT_ENV, "OPENROUTER_API_KEY"))
    meta_secret_set = bool(env_get(DT_ENV, "META_APP_SECRET"))
    meta_token_set = bool(env_get(DT_ENV, "META_PAGE_TOKEN"))
    meta_page = env_get(DT_ENV, "META_PAGE_ID")
    ig_user = env_get(DT_ENV, "IG_USER_ID")
    hc_hb = env_get(ENVF, "HC_HEARTBEAT_URL")
    hc_bk = env_get(ENVF, "HC_BACKUP_URL")
    domain = env_get(ENVF, "PUBLIC_DOMAIN")

    monthly_usd = yaml_get_scalar(DT_YAML, "budget", "monthly_usd")
    alert_pct = yaml_get_scalar(DT_YAML, "budget", "alert_at_percent")
    auto_send_templates = yaml_get_scalar(DT_YAML, "autonomy", "auto_send_templates") == "true"
    current_auto = yaml_get_scalar(DT_YAML, "autonomy", "auto_intents")
    current_auto_set = {s.strip() for s in current_auto.strip("[] ").split(",") if s.strip()}
    msg_days = yaml_get_scalar(DT_YAML, "retention", "messages_days")
    appr_days = yaml_get_scalar(DT_YAML, "retention", "approvals_days")
    lead_days = yaml_get_scalar(DT_YAML, "retention", "inactive_leads_days")

    def secret_input(name: str, label: str, is_set: bool) -> str:
        status = "set — leave blank to keep it" if is_set else "not set"
        return f"""
        <label>{esc(label)} <span class="hint">({status})</span><br>
        <input type="password" name="{name}" placeholder="unchanged" autocomplete="new-password"></label>"""

    def text_input(name: str, label: str, value: str, kind: str = "text") -> str:
        return f"""
        <label>{esc(label)}<br>
        <input type="{kind}" name="{name}" value="{esc(value)}"></label>"""

    def checkbox(name: str, label: str, checked: bool) -> str:
        c = "checked" if checked else ""
        return f'<label class="row"><input type="checkbox" name="{name}" {c}> {esc(label)}</label>'

    auto_checks = "\n".join(
        checkbox(f"auto_{i}", i, i in current_auto_set) for i in AUTO_INTENT_CHOICES
    )

    banner = f'<p class="msg">{esc(message)}</p>' if message else ""

    return layout("/settings", f"""{banner}
<form method="post" action="/settings/save">

<fieldset><legend>Telegram</legend>
{text_input("owner", "Your Telegram user ID", owner)}
{secret_input("hermes_bot", "Token of @SakirAI_bot (Hermes)", hermes_bot_set)}
{secret_input("sales_bot", "Token of @DTSalesDesk_bot (approvals)", sales_bot_set)}
</fieldset>

<fieldset><legend>OpenRouter</legend>
{secret_input("or_hermes", "Key for Hermes (your assistant's own brain)", or_hermes_set)}
{secret_input("or_sales", "Key for Sales (budget below)", or_sales_set)}
</fieldset>

<fieldset><legend>Facebook / Instagram</legend>
{secret_input("meta_secret", "Meta App Secret", meta_secret_set)}
{text_input("meta_page", "Facebook Page ID", meta_page)}
{secret_input("meta_token", "Facebook Page access token", meta_token_set)}
{text_input("ig_user", "Instagram business account ID", ig_user)}
</fieldset>

<fieldset><legend>Outside monitor (healthchecks.io — optional)</legend>
{text_input("hc_hb", "Heartbeat ping URL", hc_hb)}
{text_input("hc_bk", "Backup ping URL", hc_bk)}
</fieldset>

<fieldset><legend>Sales budget</legend>
{text_input("monthly_usd", "Monthly budget (USD)", monthly_usd, "number")}
{text_input("alert_pct", "Alert at % of budget", alert_pct, "number")}
</fieldset>

<fieldset><legend>Autonomy — intents the assistant may send without your approval</legend>
<p class="hint">price, discount, order, complaint and legal can never be made automatic here
(or anywhere else) — see AGENTS.md rule&nbsp;6.</p>
{auto_checks}
{checkbox("auto_send_templates", "Also auto-send saved FAQ templates", auto_send_templates)}
</fieldset>

<fieldset><legend>Data retention (days; 0 = keep forever)</legend>
{text_input("msg_days", "Customer messages", msg_days, "number")}
{text_input("appr_days", "Decided approvals", appr_days, "number")}
{text_input("lead_days", "Inactive leads", lead_days, "number")}
</fieldset>

<fieldset><legend>Domain (read only — see docs/OPERATIONS.md to change)</legend>
<p class="readonly">{esc(domain) or "not set"} — changing this needs
<code>install.sh --step nginx</code> and <code>--step tls</code> on the server, not this page.</p>
</fieldset>

<button type="submit">Save &amp; apply</button>
</form>
""")


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    denied = require_login(request)
    if denied:
        return denied
    return render_dashboard()


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    denied = require_login(request)
    if denied:
        return denied
    return render_settings()


@app.post("/settings/save", response_class=HTMLResponse)
async def save(request: Request):
    denied = require_login(request)
    if denied:
        return denied
    form = await request.form()

    def f(name: str) -> str:
        return str(form.get(name, "")).strip()

    touched: set[str] = set()

    owner = f("owner")
    if owner:
        env_set(DT_ENV, "TELEGRAM_OWNER_ID", owner)
        env_set(SAFE_ENV, "TELEGRAM_OWNER_ID", owner)
        env_set(HERMES_ENV, "TELEGRAM_ALLOWED_USERS", owner)
        touched |= {"dt-assistant", "safe-exec", "hermes"}

    if f("hermes_bot"):
        env_set(SAFE_ENV, "TELEGRAM_BOT_TOKEN", f("hermes_bot"))
        env_set(HERMES_ENV, "TELEGRAM_BOT_TOKEN", f("hermes_bot"))
        touched |= {"safe-exec", "hermes"}
    if f("sales_bot"):
        env_set(DT_ENV, "SALES_BOT_TOKEN", f("sales_bot")); touched.add("dt-assistant")
    if f("or_hermes"):
        env_set(HERMES_ENV, "OPENROUTER_API_KEY", f("or_hermes")); touched.add("hermes")
    if f("or_sales"):
        env_set(DT_ENV, "OPENROUTER_API_KEY", f("or_sales")); touched.add("dt-assistant")
    if f("meta_secret"):
        env_set(DT_ENV, "META_APP_SECRET", f("meta_secret")); touched.add("dt-assistant")
    if f("meta_token"):
        env_set(DT_ENV, "META_PAGE_TOKEN", f("meta_token")); touched.add("dt-assistant")
    if f("meta_page"):
        env_set(DT_ENV, "META_PAGE_ID", f("meta_page")); touched.add("dt-assistant")
    if f("ig_user"):
        env_set(DT_ENV, "IG_USER_ID", f("ig_user")); touched.add("dt-assistant")

    # Outside monitor URLs: read fresh by the next cron run, no restart needed.
    env_set(ENVF, "HC_HEARTBEAT_URL", f("hc_hb"))
    env_set(ENVF, "HC_BACKUP_URL", f("hc_bk"))

    errors: list[str] = []

    for yaml_key, field_name, section, key in (
        ("monthly_usd", "monthly_usd", "budget", "monthly_usd"),
        ("alert_pct", "alert_pct", "budget", "alert_at_percent"),
        ("msg_days", "msg_days", "retention", "messages_days"),
        ("appr_days", "appr_days", "retention", "approvals_days"),
        ("lead_days", "lead_days", "retention", "inactive_leads_days"),
    ):
        raw = f(field_name)
        if raw == "":
            continue
        if not raw.isdigit():
            errors.append(f"{field_name}: must be a whole number, got {raw!r}")
            continue
        yaml_set_scalar(DT_YAML, section, key, raw)
        touched.add("dt-assistant")

    chosen_intents = {i for i in AUTO_INTENT_CHOICES if form.get(f"auto_{i}")}
    unsafe = chosen_intents & HARD_NEVER_AUTO
    if unsafe:
        # Can't happen through the checkboxes themselves (they only list safe
        # intents) — this only fires against a hand-crafted request, and it
        # must still refuse, matching the CI assertion and AGENTS.md rule 6.
        errors.append(f"refused: {sorted(unsafe)} may never be automatic")
    else:
        yaml_set_scalar(DT_YAML, "autonomy", "auto_intents",
                         "[" + ", ".join(sorted(chosen_intents)) + "]")
        yaml_set_scalar(DT_YAML, "autonomy", "auto_send_templates",
                         "true" if form.get("auto_send_templates") else "false")
        touched.add("dt-assistant")

    log = ""
    if touched and not errors:
        log = apply(*sorted(touched))

    parts = []
    if touched:
        parts.append(f"Saved. Restarted: {', '.join(sorted(touched))}.")
    else:
        parts.append("Nothing changed.")
    if errors:
        parts.append("Problems:\n- " + "\n- ".join(errors))
    if log:
        parts.append("\n" + log[-2000:])
    return render_settings("\n\n".join(parts))
