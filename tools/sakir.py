#!/usr/bin/env python3
"""
sakir.py — the one tool Hermes skills use to act on Sakir AI services.

Mounted read-only into the Hermes container at /opt/sakir-tools/sakir.py.
Standard library only, so it runs with any Python 3.9+ without installs.
Reads its endpoints and tokens from the container environment
(secrets/hermes.env): SAFE_EXEC_URL, SAFE_EXEC_TOKEN, DT_ASSISTANT_URL,
INTERNAL_API_TOKEN, STT_URL, TTS_URL.

Usage (python3 /opt/sakir-tools/sakir.py <group> <command> ...):

  server status                       containers and health
  server logs <container> [--tail N]  recent logs (max 500 lines)
  server errors                       error lines per container, last hour
  server disk | ssl | nginx-test | reboot-check   host checks (waits for the result)
  server restart <container> --reason "..."      safe: runs, Sakir is told
  server nginx-reload | ssl-renew --reason "..."  safe
  server reboot | poweroff | prune-images --reason "..."   risky: code to Sakir
  server remove <container> --reason "..."                 risky
  server confirm <request-id> <code>  approve a risky request (code from Sakir)
  server pending                      risky requests waiting for a code

  sales summary [--days N]            leads, messages, approvals, spend
  sales leads [text]                  find leads by name/business/phone
  sales inbox                         drafts waiting in @DTSalesDesk_bot
  sales spend                         model spend this month
  sales pause | resume                stop/start automatic customer replies

  content schedule --product P --platform F --at "YYYY-MM-DD HH:MM" (--caption TEXT | --caption-file PATH) [--media PATH]
                                      add an APPROVED post (Asia/Dhaka time)
  content calendar [--days N]         upcoming posts

  kb search <collection> <query>      search the knowledge base (restora, me, ops)
  kb remember <text>                  save a note to knowledge/inbox for review

  voice transcribe <audio-file>       Bangla/English speech to text
  voice speak <text> [--lang bn|en] [--out PATH]   text to MP3

Exit code 0 on success; errors are printed to stderr with exit code 1.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

SAFE_EXEC = os.environ.get("SAFE_EXEC_URL", "http://safe-exec:8080")
SAFE_TOKEN = os.environ.get("SAFE_EXEC_TOKEN", "")
DT = os.environ.get("DT_ASSISTANT_URL", "http://dt-assistant:8080")
DT_TOKEN = os.environ.get("INTERNAL_API_TOKEN", "")
STT = os.environ.get("STT_URL", "http://stt:8000")
TTS = os.environ.get("TTS_URL", "http://tts:8000")
QDRANT = os.environ.get("QDRANT_URL", "http://qdrant:6333")
INBOX = Path(os.environ.get("KNOWLEDGE_INBOX", "/knowledge/inbox"))


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def request(method: str, url: str, token: str = "", body: dict | None = None,
            data: bytes | None = None, content_type: str | None = None, timeout: int = 60) -> object:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode()
        content_type = "application/json"
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if resp.headers.get_content_type() == "application/json":
                return json.loads(raw or b"null")
            return raw
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        try:
            detail = json.loads(detail).get("detail", detail)
        except (ValueError, AttributeError):
            pass
        fail(f"{method} {url} -> HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        fail(f"cannot reach {url}: {exc.reason}")


def multipart(fields: dict[str, str], file_field: str, path: Path) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; '
                 f'filename="{path.name}"\r\nContent-Type: {ctype}\r\n\r\n'.encode())
    parts.append(path.read_bytes())
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def show(obj: object) -> None:
    if isinstance(obj, (dict, list)):
        print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))
    elif isinstance(obj, bytes):
        print(obj.decode(errors="replace"))
    else:
        print(obj)


# ---------------------------------------------------------------------------
# server -> safe-exec
# ---------------------------------------------------------------------------
def safe_run(action: str, args: dict | None = None, reason: str = "") -> object:
    if not SAFE_TOKEN:
        fail("SAFE_EXEC_TOKEN is not set in the Hermes environment")
    result = request("POST", f"{SAFE_EXEC}/run", SAFE_TOKEN,
                     {"action": action, "args": args or {}, "reason": reason})
    # Host actions are queued; wait up to 90 s for the root runner's result.
    inner = result.get("result") if isinstance(result, dict) else None
    if isinstance(inner, dict) and "queued" in inner:
        job = inner["queued"]
        for _ in range(45):
            time.sleep(2)
            done = request("GET", f"{SAFE_EXEC}/result/{job}", SAFE_TOKEN)
            if isinstance(done, dict) and done.get("status") == "done":
                return done
        return {"status": "still running", "job": job, "hint": f"check later: server result {job}"}
    return result


def cmd_server(a: argparse.Namespace) -> None:
    c = a.command
    simple = {"status": "containers_status", "errors": "error_summary", "disk": "disk_usage",
              "ssl": "ssl_expiry", "nginx-test": "nginx_test",
              "reboot-check": "reboot_required"}
    reasoned = {"nginx-reload": "nginx_reload", "ssl-renew": "ssl_renew", "reboot": "reboot",
                "poweroff": "poweroff", "prune-images": "prune_images"}
    if c in simple:
        show(safe_run(simple[c]))
    elif c in reasoned:
        if not a.reason:
            fail("--reason is required for this action")
        show(safe_run(reasoned[c], reason=a.reason))
    elif c == "logs":
        if not a.name:
            fail("usage: server logs <container> [--tail N]")
        show(safe_run("container_logs", {"name": a.name, "tail": a.tail}))
    elif c in ("restart", "remove"):
        if not a.name or not a.reason:
            fail(f"usage: server {c} <container> --reason \"...\"")
        show(safe_run("restart_container" if c == "restart" else "remove_container", {"name": a.name}, a.reason))
    elif c == "confirm":
        if not a.name or not a.code:
            fail("usage: server confirm <request-id> <code>")
        show(request("POST", f"{SAFE_EXEC}/confirm", SAFE_TOKEN, {"id": a.name, "code": a.code}))
    elif c == "pending":
        show(request("GET", f"{SAFE_EXEC}/pending", SAFE_TOKEN))
    elif c == "result":
        show(request("GET", f"{SAFE_EXEC}/result/{a.name}", SAFE_TOKEN))
    else:
        fail(f"unknown server command: {c}")


# ---------------------------------------------------------------------------
# sales / content -> dt-assistant internal API
# ---------------------------------------------------------------------------
def dt(method: str, path: str, body: dict | None = None) -> object:
    if not DT_TOKEN:
        fail("INTERNAL_API_TOKEN is not set in the Hermes environment")
    return request(method, f"{DT}{path}", DT_TOKEN, body)


def cmd_sales(a: argparse.Namespace) -> None:
    c = a.command
    if c == "summary":
        show(dt("GET", f"/internal/summary?days={a.days}"))
    elif c == "leads":
        show(dt("GET", "/internal/leads?" + urllib.parse.urlencode({"q": " ".join(a.text or [])})))
    elif c == "inbox":
        show(dt("GET", "/internal/approvals"))
    elif c == "spend":
        show(dt("GET", "/internal/spend"))
    elif c in ("pause", "resume"):
        show(dt("POST", f"/internal/{c}"))
    else:
        fail(f"unknown sales command: {c}")


def cmd_content(a: argparse.Namespace) -> None:
    if a.command == "calendar":
        show(dt("GET", f"/internal/calendar?days={a.days}"))
        return
    if a.command != "schedule":
        fail(f"unknown content command: {a.command}")
    if not (a.product and a.platform and a.at):
        fail("schedule needs --product, --platform and --at")
    caption = a.caption or (Path(a.caption_file).read_text(encoding="utf-8") if a.caption_file else "")
    if not caption.strip():
        fail("schedule needs --caption or --caption-file")
    try:
        when = datetime.strptime(a.at, "%Y-%m-%d %H:%M").isoformat()
    except ValueError:
        fail("--at must look like 2026-11-02 10:00 (Asia/Dhaka time)")
    media = a.media.removeprefix("/outbox/") if a.media else None
    show(dt("POST", "/internal/calendar", {"product": a.product, "platform": a.platform,
                                           "publish_at": when, "caption": caption, "media_path": media}))


# ---------------------------------------------------------------------------
# knowledge
# ---------------------------------------------------------------------------
def cmd_kb(a: argparse.Namespace) -> None:
    if a.command == "remember":
        text = " ".join(a.text or []).strip()
        if not text:
            fail("usage: kb remember <text>")
        INBOX.mkdir(parents=True, exist_ok=True)
        path = INBOX / f"{datetime.now():%Y-%m-%d}.md"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"- {datetime.now():%H:%M} {text}\n")
        show({"saved_to": str(path)})
    elif a.command == "search":
        if not a.text or len(a.text) < 2:
            fail("usage: kb search <collection> <query>")
        collection, query = a.text[0], " ".join(a.text[1:])
        vec = request("POST", f"{STT}/embed", body={"text": query, "kind": "query"})["vector"]
        hits = request("POST", f"{QDRANT}/collections/{collection}/points/search",
                       body={"vector": vec, "limit": 5, "with_payload": True})
        show([{"score": round(h["score"], 3), **h["payload"]} for h in hits.get("result", [])])
    else:
        fail(f"unknown kb command: {a.command}")


# ---------------------------------------------------------------------------
# voice
# ---------------------------------------------------------------------------
def cmd_voice(a: argparse.Namespace) -> None:
    if a.command == "transcribe":
        if not a.text:
            fail("usage: voice transcribe <audio-file>")
        path = Path(a.text[0])
        if not path.is_file():
            fail(f"file not found: {path}")
        data, ctype = multipart({"language": "auto"}, "file", path)
        show(request("POST", f"{STT}/transcribe", data=data, content_type=ctype, timeout=600))
    elif a.command == "speak":
        text = " ".join(a.text or []).strip()
        if not text:
            fail("usage: voice speak <text> [--lang bn|en] [--out PATH]")
        audio = request("POST", f"{TTS}/speak", body={"text": text, "lang": a.lang}, timeout=120)
        out = Path(a.out or f"/outbox/voice/reply-{datetime.now():%Y%m%d-%H%M%S}.mp3")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(audio if isinstance(audio, bytes) else b"")
        show({"audio": str(out)})
    else:
        fail(f"unknown voice command: {a.command}")


# ---------------------------------------------------------------------------
def main() -> None:
    p = argparse.ArgumentParser(prog="sakir.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("group", choices=["server", "sales", "content", "kb", "voice"])
    p.add_argument("command")
    p.add_argument("name", nargs="?")                 # container / request id / job id
    p.add_argument("code", nargs="?")                 # approval code
    p.add_argument("--reason", default="")
    p.add_argument("--tail", type=int, default=200)
    p.add_argument("--days", type=int, default=1)
    p.add_argument("--product")
    p.add_argument("--platform")
    p.add_argument("--at")
    p.add_argument("--caption")
    p.add_argument("--caption-file")
    p.add_argument("--media")
    p.add_argument("--lang", default="bn", choices=["bn", "en"])
    p.add_argument("--out")
    a, rest = p.parse_known_args()
    # Free text (queries, notes, file paths) = everything after the command.
    a.text = ([a.name] if a.name else []) + ([a.code] if a.code else []) + rest

    {"server": cmd_server, "sales": cmd_sales, "content": cmd_content,
     "kb": cmd_kb, "voice": cmd_voice}[a.group](a)


if __name__ == "__main__":
    main()
