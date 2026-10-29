"""
safe-exec — the only way Sakir AI agents act on the server.

Agents (Hermes skills via tools/sakir.py) call this API with a bearer token.
Every request names an ACTION from config/allowlist.yaml; there is no way to
pass a shell command. Tiers:

    read   run now, return the result
    safe   run now, return the result, tell Sakir on Telegram ("Done: ...")
    risky  send a 4-digit code to Sakir's Telegram and wait; runs only after
           POST /confirm with the right code within the time limit
           (Sakir sends Hermes "confirm <id> <code>"; Hermes calls /confirm)

Container actions use the Docker API (this container mounts the socket).
Host actions (nginx, certbot, reboot, poweroff) are written as job files to
/hostops/queue; the root runner `sakir-hostops` on the host executes them and
writes results to /hostops/done.

Endpoints
    GET  /health                liveness (no auth)
    POST /run                   {"action": "...", "args": {...}, "reason": "..."}
    POST /confirm               {"id": "...", "code": "1234"}
    GET  /result/{job_id}       result of a queued host action
    GET  /pending               approval requests waiting for a code
"""
from __future__ import annotations

import glob
import json
import logging
import os
import re
import secrets
import threading
import time
from typing import Any

import docker
import requests
import yaml
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TOKEN = os.environ["SAFE_EXEC_TOKEN"]
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")      # used only to SEND messages
OWNER_ID = os.environ.get("TELEGRAM_OWNER_ID", "")
ALLOWLIST_PATH = os.environ.get("ALLOWLIST_PATH", "/app/allowlist.yaml")
QUEUE_DIR = "/hostops/queue"
DONE_DIR = "/hostops/done"
BACKUP_DIR = "/backups"
AUDIT_PATH = "/app/audit/actions.log"
LOKI_URL = os.environ.get("LOKI_URL", "http://loki:3100")

with open(ALLOWLIST_PATH, encoding="utf-8") as fh:
    ALLOW: dict[str, Any] = yaml.safe_load(fh)

TIERS: dict[str, str] = ALLOW["tiers"]
APPROVAL = ALLOW.get("approval", {})
CODE_TTL = int(APPROVAL.get("code_ttl_seconds", 600))
MAX_ATTEMPTS = int(APPROVAL.get("max_attempts", 3))
BACKUP_MAX_AGE = int(APPROVAL.get("backup_max_age_hours", 24)) * 3600

logging.basicConfig(level=logging.INFO, format="%(asctime)s safe-exec %(levelname)s %(message)s")
log = logging.getLogger("safe-exec")

dk = docker.from_env()
app = FastAPI(title="safe-exec", docs_url=None, redoc_url=None, openapi_url=None)

# Approval requests waiting for a code. In memory on purpose: a restart
# cancels every pending request, which is the safe direction.
_pending: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()

NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,62}$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def require_token(authorization: str = Header(default="")) -> None:
    """Constant-time bearer token check."""
    if not secrets.compare_digest(authorization, f"Bearer {TOKEN}"):
        raise HTTPException(status_code=401, detail="unauthorized")


def audit(event: str, **data: Any) -> None:
    """Append one JSON line to the audit log and the container log (-> Loki)."""
    record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": event, **data}
    line = json.dumps(record, ensure_ascii=False, default=str)
    log.info(line)
    try:
        with open(AUDIT_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as exc:  # audit must never break an action
        log.error("audit write failed: %s", exc)


def telegram(text: str) -> bool:
    """Send a plain-text message to Sakir. Returns False if not configured/failed."""
    if not (TG_TOKEN and OWNER_ID):
        log.warning("telegram not configured; message not sent")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": OWNER_ID, "text": text, "disable_web_page_preview": True},
            timeout=10,
        )
        return r.ok
    except requests.RequestException as exc:
        log.error("telegram send failed: %s", exc)
        return False


def fresh_backup_exists() -> bool:
    files = glob.glob(os.path.join(BACKUP_DIR, "*.tar.age"))
    return bool(files) and (time.time() - max(os.path.getmtime(f) for f in files)) < BACKUP_MAX_AGE


def checked_name(args: dict[str, Any], allowed_key: str) -> str:
    """Return args['name'] if it is a valid name listed under allowed_key."""
    name = str(args.get("name", ""))
    if not NAME_RE.match(name) or name not in (ALLOW.get(allowed_key) or []):
        raise HTTPException(status_code=403, detail=f"'{name}' is not in {allowed_key}")
    return name


def queue_host_job(action: str) -> dict[str, str]:
    """Hand a host action to the root runner. Only the action name is passed."""
    job_id = secrets.token_hex(4)
    tmp = os.path.join(QUEUE_DIR, f".{job_id}.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"id": job_id, "action": action}, fh)
    os.rename(tmp, os.path.join(QUEUE_DIR, f"{job_id}.json"))   # atomic for the path watcher
    return {"queued": job_id, "poll": f"/result/{job_id}"}


def loki_error_summary() -> list[dict[str, Any]]:
    """Error-looking log lines per container in the last hour."""
    query = 'sum by (container) (count_over_time({container=~".+"} |~ "(?i)(error|exception|fatal|panic)" [1h]))'
    r = requests.get(f"{LOKI_URL}/loki/api/v1/query", params={"query": query}, timeout=10)
    r.raise_for_status()
    rows = [
        {"container": res["metric"].get("container", "?"), "errors_last_hour": int(float(res["value"][1]))}
        for res in r.json().get("data", {}).get("result", [])
    ]
    return sorted(rows, key=lambda x: -x["errors_last_hour"])


def execute(action: str, args: dict[str, Any]) -> Any:
    """Run an allowlisted action. Callers have already checked tier/approval."""
    if action == "containers_status":
        out = []
        for c in dk.containers.list(all=True):
            health = (c.attrs.get("State", {}).get("Health") or {}).get("Status", "none")
            out.append({"name": c.name, "status": c.status, "health": health})
        return sorted(out, key=lambda x: x["name"])

    if action == "container_logs":
        name = checked_name(args, "containers")
        tail = max(1, min(int(args.get("tail", 200)), 500))
        return dk.containers.get(name).logs(tail=tail, timestamps=True).decode("utf-8", "replace")

    if action == "error_summary":
        return loki_error_summary()

    if action == "restart_container":
        name = checked_name(args, "restartable")
        dk.containers.get(name).restart(timeout=30)
        return f"{name} restarted"

    if action == "remove_container":
        name = checked_name(args, "removable")
        dk.containers.get(name).remove(force=True)
        return f"{name} removed"

    if action == "prune_images":
        result = dk.images.prune(filters={"dangling": True})
        return {"space_reclaimed_mb": round((result.get("SpaceReclaimed") or 0) / 1e6, 1)}

    if action in (ALLOW.get("host_actions") or []):
        return queue_host_job(action)

    raise HTTPException(status_code=403, detail="not on allowlist")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
class RunRequest(BaseModel):
    action: str = Field(..., max_length=64)
    args: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(default="", max_length=500)


class ConfirmRequest(BaseModel):
    id: str = Field(..., max_length=16)
    code: str = Field(..., max_length=8)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/run", dependencies=[Depends(require_token)])
def run(req: RunRequest) -> dict[str, Any]:
    tier = TIERS.get(req.action)
    if tier is None:
        audit("refused", action=req.action, args=req.args, reason=req.reason)
        raise HTTPException(status_code=403, detail="not on allowlist")

    if tier == "risky":
        if req.action in ("reboot", "poweroff") and not fresh_backup_exists():
            audit("blocked_no_backup", action=req.action)
            return {"status": "blocked", "reason": "no backup in the allowed window; run a backup first"}

        request_id = secrets.token_hex(3)
        code = f"{secrets.randbelow(10000):04d}"
        sent = telegram(
            f"APPROVAL NEEDED [{request_id}]\n"
            f"Action: {req.action} {json.dumps(req.args) if req.args else ''}\n"
            f"Why: {req.reason or '-'}\n\n"
            f"To approve, send Hermes this message:\nconfirm {request_id} {code}\n"
            f"(expires in {CODE_TTL // 60} min; ignore this message to cancel)"
        )
        if not sent:
            audit("approval_not_sent", action=req.action)
            raise HTTPException(status_code=503, detail="could not reach Sakir on Telegram; nothing was done")
        with _lock:
            _pending[request_id] = {
                "action": req.action, "args": req.args, "code": code,
                "expires": time.time() + CODE_TTL, "attempts": 0,
            }
        audit("approval_requested", id=request_id, action=req.action, args=req.args, reason=req.reason)
        # The code is NOT returned: it only exists in Sakir's Telegram chat.
        return {"status": "waiting_approval", "id": request_id, "expires_in_seconds": CODE_TTL}

    result = execute(req.action, req.args)
    audit("ran", action=req.action, args=req.args, tier=tier, reason=req.reason)
    if tier == "safe":
        telegram(f"Done: {req.action} {json.dumps(req.args) if req.args else ''}".strip())
    return {"status": "ok", "tier": tier, "result": result}


@app.post("/confirm", dependencies=[Depends(require_token)])
def confirm(req: ConfirmRequest) -> dict[str, Any]:
    with _lock:
        item = _pending.get(req.id)
        if not item or time.time() > item["expires"]:
            _pending.pop(req.id, None)
            raise HTTPException(status_code=410, detail="unknown or expired request")
        item["attempts"] += 1
        if not secrets.compare_digest(req.code.strip(), item["code"]):
            if item["attempts"] >= MAX_ATTEMPTS:
                _pending.pop(req.id, None)
                audit("approval_cancelled", id=req.id, action=item["action"])
                telegram(f"Request [{req.id}] cancelled after {MAX_ATTEMPTS} wrong codes.")
            else:
                audit("approval_wrong_code", id=req.id, attempts=item["attempts"])
            raise HTTPException(status_code=403, detail="wrong code")
        _pending.pop(req.id, None)

    result = execute(item["action"], item["args"])
    audit("approved_and_ran", id=req.id, action=item["action"], args=item["args"])
    telegram(f"Approved and started: {item['action']}")
    return {"status": "ok", "result": result}


@app.get("/result/{job_id}", dependencies=[Depends(require_token)])
def result(job_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{8}", job_id):
        raise HTTPException(status_code=400, detail="bad job id")
    path = os.path.join(DONE_DIR, f"{job_id}.json")
    if not os.path.exists(path):
        return {"status": "pending"}
    with open(path, encoding="utf-8") as fh:
        return {"status": "done", **json.load(fh)}


@app.get("/pending", dependencies=[Depends(require_token)])
def pending() -> list[dict[str, Any]]:
    now = time.time()
    with _lock:
        return [
            {"id": k, "action": v["action"], "args": v["args"], "expires_in_seconds": int(v["expires"] - now)}
            for k, v in _pending.items() if v["expires"] > now
        ]
