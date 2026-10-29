"""
dt-assistant HTTP app.

Public (through host Nginx):
  GET  /meta/webhook      Meta verification handshake
  POST /meta/webhook      Meta events (signature checked, then queued)

Container network only (Bearer INTERNAL_API_TOKEN; used by Hermes skills):
  GET  /internal/summary?days=1      numbers for briefs
  GET  /internal/leads?q=&limit=     find leads
  GET  /internal/approvals           drafts waiting
  GET  /internal/calendar?days=7     upcoming posts
  POST /internal/calendar            add an APPROVED post
  GET  /internal/spend               model spend this month
  POST /internal/pause | /internal/resume

Health:
  GET  /health
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import secrets as pysecrets
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from .config import LOCAL_TZ, load_secrets, load_settings
from .db import Database
from .knowledge import Knowledge
from .llm import LLM
from .meta import GraphClient, InboundEvent, parse_webhook, verify_signature
from .pipeline import Assistant
from .telegram import SalesDesk

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("dt.main")

PLATFORMS = {"facebook", "instagram", "youtube", "linkedin", "tiktok", "x"}


class State:
    """Everything created at start-up, shared by routes and workers."""
    secrets = load_secrets()
    settings = load_settings()
    db: Database
    assistant: Assistant
    queue: asyncio.Queue[InboundEvent]


S = State()


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------
async def event_worker() -> None:
    """Processes webhook events one at a time (keeps per-lead order)."""
    while True:
        ev = await S.queue.get()
        try:
            await S.assistant.handle_event(ev)
        except Exception:
            log.exception("failed to handle event %s", ev.meta_id)
        finally:
            S.queue.task_done()


async def scheduler() -> None:
    """Runs the periodic jobs; one failing job never stops the others."""
    s = S.settings
    every = {
        "publisher": int(s.get("publisher", "check_every_seconds", default=60)),
        "followup": int(s.get("followup", "check_every_minutes", default=30)) * 60,
        "stale": 600,
        "metrics": 60,
    }
    jobs = {
        "publisher": S.assistant.publisher_tick,
        "followup": S.assistant.followup_tick,
        "stale": S.assistant.stale_tick,
        "metrics": S.assistant.metrics_tick,
    }
    last: dict[str, float] = {name: 0.0 for name in jobs}
    loop = asyncio.get_running_loop()
    while True:
        now = loop.time()
        for name, job in jobs.items():
            if now - last[name] >= every[name]:
                last[name] = now
                try:
                    await job()
                except Exception:
                    log.exception("scheduled job %s failed", name)
        await asyncio.sleep(15)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    sec, st = S.secrets, S.settings
    S.db = Database(sec.database_url)
    await S.db.connect()
    desk = SalesDesk(sec.sales_bot_token, sec.owner_id)
    llm = LLM(sec.openrouter_key, st, S.db, notify=desk.send)
    graph = GraphClient(sec.meta_page_id, sec.meta_page_token, st.graph_version, sec.ig_user_id)
    kb = Knowledge(sec.stt_url, sec.qdrant_url, st.collection)
    S.assistant = Assistant(sec, st, S.db, llm, graph, kb, desk)
    S.queue = asyncio.Queue(maxsize=1000)

    missing = [name for name, ok in [("Meta", sec.meta_ready), ("Sales desk bot", sec.telegram_ready),
                                     ("OpenRouter", llm.configured)] if not ok]
    if missing:
        log.warning("not configured yet: %s (the service runs; those parts stay off)", ", ".join(missing))
    if not kb.pricing_ready():
        log.warning("knowledge/products/dt-restora/pricing.md has TODOs; price drafts will be flagged")

    tasks = [asyncio.create_task(event_worker(), name="events"),
             asyncio.create_task(desk.run(S.assistant), name="sales-desk"),
             asyncio.create_task(scheduler(), name="scheduler")]
    log.info("dt-assistant started")
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()
        for t in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await t
        for closer in (desk.close, llm.close, graph.close, kb.close, S.db.close):
            with contextlib.suppress(Exception):
                await closer()


app = FastAPI(title="dt-assistant", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


# ---------------------------------------------------------------------------
# Public: Meta webhook
# ---------------------------------------------------------------------------
@app.get("/meta/webhook")
async def meta_verify(mode: str = Query("", alias="hub.mode"),
                      token: str = Query("", alias="hub.verify_token"),
                      challenge: str = Query("", alias="hub.challenge")) -> PlainTextResponse:
    expected = S.secrets.meta_verify_token
    if mode == "subscribe" and expected and pysecrets.compare_digest(token, expected):
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=403, detail="verification failed")


@app.post("/meta/webhook")
async def meta_event(request: Request) -> PlainTextResponse:
    body = await request.body()
    if not S.secrets.meta_app_secret:
        raise HTTPException(status_code=503, detail="META_APP_SECRET not configured")
    if not verify_signature(S.secrets.meta_app_secret, body, request.headers.get("x-hub-signature-256")):
        log.warning("rejected webhook with bad signature from %s", request.client.host if request.client else "?")
        raise HTTPException(status_code=401, detail="bad signature")
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid JSON")
    for ev in parse_webhook(payload, S.secrets.meta_page_id, S.secrets.ig_user_id):
        try:
            S.queue.put_nowait(ev)
        except asyncio.QueueFull:
            log.error("event queue full; dropping %s", ev.meta_id)
    # Meta expects a fast 200; processing happens in the background worker.
    return PlainTextResponse("EVENT_RECEIVED")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict[str, Any]:
    try:
        db_ok = await S.db.ping()
    except Exception:
        db_ok = False
    if not db_ok:
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ok", "meta": S.secrets.meta_ready, "sales_desk": S.secrets.telegram_ready,
            "llm": bool(S.secrets.openrouter_key), "queue": S.queue.qsize(),
            "paused": bool(await S.db.get_setting("paused", False))}


# ---------------------------------------------------------------------------
# Internal API (Hermes)
# ---------------------------------------------------------------------------
def internal_auth(authorization: str = Header(default="")) -> None:
    token = S.secrets.internal_token
    if not token or not pysecrets.compare_digest(authorization, f"Bearer {token}"):
        raise HTTPException(status_code=401, detail="unauthorized")


def _row(r: Any) -> dict[str, Any]:
    out = dict(r)
    for k, v in out.items():
        if isinstance(v, datetime):
            out[k] = v.astimezone(LOCAL_TZ).isoformat(timespec="minutes")
    return out


internal = Depends(internal_auth)


@app.get("/internal/summary", dependencies=[internal])
async def internal_summary(days: int = Query(1, ge=1, le=90)) -> dict[str, Any]:
    data = await S.db.summary(days)
    data["paused"] = bool(await S.db.get_setting("paused", False))
    return data


@app.get("/internal/leads", dependencies=[internal])
async def internal_leads(q: str = "", limit: int = Query(10, ge=1, le=50)) -> list[dict[str, Any]]:
    return [_row(r) for r in await S.db.search_leads(q, limit)]


@app.get("/internal/approvals", dependencies=[internal])
async def internal_approvals() -> list[dict[str, Any]]:
    return [_row(r) for r in await S.db.waiting_approvals(50)]


@app.get("/internal/calendar", dependencies=[internal])
async def internal_calendar(days: int = Query(7, ge=1, le=60)) -> list[dict[str, Any]]:
    return [_row(r) for r in await S.db.calendar(days)]


class CalendarItem(BaseModel):
    product: str = Field(..., max_length=40)
    platform: str
    publish_at: datetime                       # ISO 8601; no offset = Asia/Dhaka
    caption: str = Field(..., min_length=1, max_length=5000)
    media_path: str | None = Field(default=None, max_length=300)


@app.post("/internal/calendar", dependencies=[internal])
async def internal_calendar_add(item: CalendarItem) -> dict[str, Any]:
    """Only call this for content Sakir has APPROVED; it will be published at publish_at."""
    if item.platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"platform must be one of {sorted(PLATFORMS)}")
    when = item.publish_at if item.publish_at.tzinfo else item.publish_at.replace(tzinfo=LOCAL_TZ)
    if item.media_path:
        try:
            S.assistant._media_path(item.media_path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    post_id = await S.db.add_calendar(item.product, item.platform, when, item.caption, item.media_path)
    return {"id": post_id, "publish_at": when.astimezone(LOCAL_TZ).isoformat(timespec="minutes")}


@app.get("/internal/spend", dependencies=[internal])
async def internal_spend() -> dict[str, Any]:
    limit = float(S.settings.get("budget", "monthly_usd", default=26))
    spent = await S.db.month_spend()
    return {"month_usd": round(spent, 4), "limit_usd": limit,
            "by_purpose": [dict(r) for r in await S.db.spend_by_purpose()]}


@app.post("/internal/pause", dependencies=[internal])
async def internal_pause() -> dict[str, bool]:
    await S.db.set_setting("paused", True)
    return {"paused": True}


@app.post("/internal/resume", dependencies=[internal])
async def internal_resume() -> dict[str, bool]:
    await S.db.set_setting("paused", False)
    return {"paused": False}
