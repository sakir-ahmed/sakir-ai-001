"""
Database access (asyncpg). All SQL lives here so the rest of the app reads
like the business process it implements.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import asyncpg

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class Database:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.pool: asyncpg.Pool | None = None

    # ---- lifecycle -----------------------------------------------------------
    async def connect(self) -> None:
        async def _init(conn: asyncpg.Connection) -> None:
            await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")

        self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=5, init=_init)
        async with self.pool.acquire() as conn:
            await conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    @property
    def p(self) -> asyncpg.Pool:
        assert self.pool is not None, "database not connected"
        return self.pool

    async def ping(self) -> bool:
        return (await self.p.fetchval("SELECT 1")) == 1

    # ---- settings (key/value) -------------------------------------------------
    async def get_setting(self, key: str, default: Any = None) -> Any:
        value = await self.p.fetchval("SELECT value FROM settings WHERE key = $1", key)
        return default if value is None else value

    async def set_setting(self, key: str, value: Any) -> None:
        """Store a JSON value; None deletes the key."""
        if value is None:
            await self.p.execute("DELETE FROM settings WHERE key = $1", key)
            return
        await self.p.execute(
            """INSERT INTO settings (key, value, updated_at) VALUES ($1, $2, now())
               ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()""",
            key, value,
        )

    # ---- leads -----------------------------------------------------------------
    async def upsert_lead(self, channel_user_id: str, source: str, name: str | None, product: str) -> asyncpg.Record:
        return await self.p.fetchrow(
            """INSERT INTO leads (channel_user_id, source, name, product, last_inbound_at)
               VALUES ($1, $2, $3, $4, now())
               ON CONFLICT (channel_user_id) DO UPDATE
                 SET last_inbound_at = now(),
                     name = COALESCE(leads.name, EXCLUDED.name)
               RETURNING *""",
            channel_user_id, source, name, product,
        )

    async def update_lead(self, lead_id: int, **fields: Any) -> None:
        allowed = {"name", "business", "phone", "stage", "language", "notes",
                   "last_outbound_at", "followup_sent_at", "holding_sent_at"}
        sets = {k: v for k, v in fields.items() if k in allowed and v not in (None, "")}
        if not sets:
            return
        cols = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(sets))
        await self.p.execute(f"UPDATE leads SET {cols} WHERE id = $1", lead_id, *sets.values())

    async def get_lead(self, lead_id: int) -> asyncpg.Record | None:
        return await self.p.fetchrow("SELECT * FROM leads WHERE id = $1", lead_id)

    async def search_leads(self, query: str, limit: int = 10) -> list[asyncpg.Record]:
        like = f"%{query}%"
        return await self.p.fetch(
            """SELECT * FROM leads
               WHERE $1 = '' OR name ILIKE $2 OR business ILIKE $2 OR phone ILIKE $2
               ORDER BY COALESCE(last_inbound_at, created_at) DESC LIMIT $3""",
            query, like, limit,
        )

    async def followup_candidates(self, stages: list[str], silence_h: float, window_h: float) -> list[asyncpg.Record]:
        """Warm leads we answered last, quiet for silence_h, still inside the window."""
        return await self.p.fetch(
            """SELECT * FROM leads
               WHERE stage = ANY($1::text[])
                 AND source IN ('messenger', 'instagram')
                 AND last_outbound_at IS NOT NULL AND last_inbound_at IS NOT NULL
                 AND last_outbound_at > last_inbound_at
                 AND now() - last_outbound_at >= make_interval(secs => $2)
                 AND now() - last_inbound_at < make_interval(secs => $3)
                 AND (followup_sent_at IS NULL OR followup_sent_at < last_inbound_at)""",
            stages, silence_h * 3600, (window_h - 1) * 3600,
        )

    # ---- messages --------------------------------------------------------------
    async def message_seen(self, meta_id: str) -> bool:
        return bool(await self.p.fetchval("SELECT 1 FROM messages WHERE meta_id = $1", meta_id))

    async def add_message(self, lead_id: int, channel: str, direction: str, text: str,
                          meta_id: str | None = None, intent: str | None = None,
                          language: str | None = None, confidence: float | None = None,
                          how: str | None = None, target_id: str | None = None) -> int | None:
        """Returns the new id, or None if meta_id was already stored (duplicate)."""
        return await self.p.fetchval(
            """INSERT INTO messages (lead_id, meta_id, channel, direction, text, intent, language,
                                     confidence, how, target_id)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
               ON CONFLICT (meta_id) DO NOTHING
               RETURNING id""",
            lead_id, meta_id, channel, direction, text, intent, language, confidence, how, target_id,
        )

    async def set_message_analysis(self, message_id: int, intent: str, language: str, confidence: float) -> None:
        await self.p.execute(
            "UPDATE messages SET intent = $2, language = $3, confidence = $4 WHERE id = $1",
            message_id, intent, language, confidence,
        )

    async def history(self, lead_id: int, limit: int = 6) -> list[asyncpg.Record]:
        rows = await self.p.fetch(
            """SELECT direction, text, created_at FROM messages
               WHERE lead_id = $1 AND text IS NOT NULL
               ORDER BY created_at DESC LIMIT $2""",
            lead_id, limit,
        )
        return list(reversed(rows))

    # ---- approvals -------------------------------------------------------------
    async def create_approval(self, lead_id: int, inbound_message_id: int | None, kind: str,
                              channel: str, target_id: str, intent: str | None, draft: str) -> int:
        return await self.p.fetchval(
            """INSERT INTO approvals (lead_id, inbound_message_id, kind, channel, target_id, intent, draft)
               VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id""",
            lead_id, inbound_message_id, kind, channel, target_id, intent, draft,
        )

    async def get_approval(self, approval_id: int) -> asyncpg.Record | None:
        return await self.p.fetchrow("SELECT * FROM approvals WHERE id = $1", approval_id)

    async def set_approval_telegram_id(self, approval_id: int, telegram_message_id: int) -> None:
        await self.p.execute("UPDATE approvals SET telegram_message_id = $2 WHERE id = $1",
                             approval_id, telegram_message_id)

    async def claim_approval(self, approval_id: int) -> asyncpg.Record | None:
        """Atomically move a waiting approval to 'sending' so a double tap cannot send twice."""
        return await self.p.fetchrow(
            """UPDATE approvals SET status = 'sending', decided_at = now()
               WHERE id = $1 AND status = 'waiting' RETURNING *""",
            approval_id,
        )

    async def finish_approval(self, approval_id: int, status: str, sent_text: str | None = None,
                              edited: bool = False, error: str | None = None) -> None:
        await self.p.execute(
            """UPDATE approvals SET status = $2, sent_text = $3, edited = $4, error = $5,
                                    decided_at = COALESCE(decided_at, now())
               WHERE id = $1""",
            approval_id, status, sent_text, edited, error,
        )

    async def waiting_approvals(self, limit: int = 20) -> list[asyncpg.Record]:
        return await self.p.fetch(
            """SELECT a.*, l.name AS lead_name, l.business AS lead_business
               FROM approvals a JOIN leads l ON l.id = a.lead_id
               WHERE a.status = 'waiting' ORDER BY a.created_at LIMIT $1""",
            limit,
        )

    async def stale_approvals(self, stale_h: float) -> list[asyncpg.Record]:
        return await self.p.fetch(
            """SELECT * FROM approvals WHERE status = 'waiting' AND NOT stale_notified
               AND now() - created_at >= make_interval(secs => $1)""",
            stale_h * 3600,
        )

    async def mark_stale_notified(self, approval_id: int) -> None:
        await self.p.execute("UPDATE approvals SET stale_notified = true WHERE id = $1", approval_id)

    # ---- content calendar ------------------------------------------------------
    async def add_calendar(self, product: str, platform: str, publish_at: datetime,
                           caption: str, media_path: str | None) -> int:
        return await self.p.fetchval(
            """INSERT INTO content_calendar (product, platform, publish_at, caption, media_path)
               VALUES ($1, $2, $3, $4, $5) RETURNING id""",
            product, platform, publish_at, caption, media_path,
        )

    async def due_posts(self) -> list[asyncpg.Record]:
        return await self.p.fetch(
            """SELECT * FROM content_calendar
               WHERE status = 'approved' AND publish_at <= now() ORDER BY publish_at LIMIT 10"""
        )

    async def set_post_status(self, post_id: int, status: str, result: str) -> None:
        await self.p.execute("UPDATE content_calendar SET status = $2, result = $3 WHERE id = $1",
                             post_id, status, result[:2000])

    async def calendar(self, days: int) -> list[asyncpg.Record]:
        return await self.p.fetch(
            """SELECT * FROM content_calendar
               WHERE publish_at BETWEEN now() - interval '1 day' AND now() + make_interval(days => $1)
               ORDER BY publish_at""",
            days,
        )

    # ---- spend -----------------------------------------------------------------
    async def add_spend(self, purpose: str, usd: float, tokens_in: int, tokens_out: int) -> None:
        await self.p.execute(
            """INSERT INTO spend (day, purpose, usd, tokens_in, tokens_out, calls)
               VALUES ((now() AT TIME ZONE 'Asia/Dhaka')::date, $1, $2, $3, $4, 1)
               ON CONFLICT (day, purpose) DO UPDATE
                 SET usd = spend.usd + EXCLUDED.usd,
                     tokens_in = spend.tokens_in + EXCLUDED.tokens_in,
                     tokens_out = spend.tokens_out + EXCLUDED.tokens_out,
                     calls = spend.calls + 1""",
            purpose, usd, tokens_in, tokens_out,
        )

    async def month_spend(self) -> float:
        value = await self.p.fetchval(
            """SELECT COALESCE(sum(usd), 0) FROM spend
               WHERE date_trunc('month', day) = date_trunc('month', (now() AT TIME ZONE 'Asia/Dhaka')::date)"""
        )
        return float(value or 0)

    async def spend_by_purpose(self) -> list[asyncpg.Record]:
        return await self.p.fetch(
            """SELECT purpose, round(sum(usd)::numeric, 4)::float AS usd, sum(calls)::int AS calls
               FROM spend
               WHERE date_trunc('month', day) = date_trunc('month', (now() AT TIME ZONE 'Asia/Dhaka')::date)
               GROUP BY purpose ORDER BY usd DESC"""
        )

    # ---- retention -------------------------------------------------------------
    async def purge_old(self, messages_days: int, approvals_days: int, leads_days: int) -> dict[str, int]:
        """Delete data older than the retention periods (0 = keep). Returns counts."""
        out = {"messages": 0, "approvals": 0, "leads": 0}

        def count(status: str) -> int:          # asyncpg returns e.g. "DELETE 12"
            return int(status.split()[-1])

        async with self.p.acquire() as conn, conn.transaction():
            if leads_days > 0:
                out["leads"] = count(await conn.execute(
                    """DELETE FROM leads WHERE stage IN ('new', 'lost')
                       AND COALESCE(last_inbound_at, created_at) < now() - make_interval(days => $1)""",
                    leads_days))
            if approvals_days > 0:
                out["approvals"] = count(await conn.execute(
                    """DELETE FROM approvals WHERE status IN ('sent', 'rejected', 'expired', 'failed')
                       AND COALESCE(decided_at, created_at) < now() - make_interval(days => $1)""",
                    approvals_days))
            if messages_days > 0:
                out["messages"] = count(await conn.execute(
                    "DELETE FROM messages WHERE created_at < now() - make_interval(days => $1)",
                    messages_days))
        return out

    # ---- metrics ---------------------------------------------------------------
    async def summary(self, days: int = 1) -> dict[str, Any]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        p = self.p
        stages = await p.fetch("SELECT stage, count(*) AS n FROM leads GROUP BY stage ORDER BY stage")
        out_how = await p.fetch(
            """SELECT COALESCE(how, 'unknown') AS how, count(*) AS n FROM messages
               WHERE direction = 'out' AND created_at >= $1 GROUP BY how""", since)
        intents = await p.fetch(
            """SELECT COALESCE(intent, 'unclassified') AS intent, count(*) AS n FROM messages
               WHERE direction = 'in' AND created_at >= $1 GROUP BY intent ORDER BY n DESC""", since)
        decided = await p.fetchrow(
            """SELECT count(*) FILTER (WHERE status = 'sent' AND NOT edited) AS approved_as_is,
                      count(*) FILTER (WHERE status = 'sent' AND edited) AS edited,
                      count(*) FILTER (WHERE status = 'rejected') AS rejected,
                      count(*) FILTER (WHERE status = 'expired') AS expired
               FROM approvals WHERE decided_at >= $1""", since)
        return {
            "period_days": days,
            "new_leads": await p.fetchval("SELECT count(*) FROM leads WHERE created_at >= $1", since),
            "messages_in": await p.fetchval(
                "SELECT count(*) FROM messages WHERE direction = 'in' AND created_at >= $1", since),
            "replies_out": {r["how"]: r["n"] for r in out_how},
            "intents": {r["intent"]: r["n"] for r in intents},
            "approvals_waiting": await p.fetchval("SELECT count(*) FROM approvals WHERE status = 'waiting'"),
            "approvals_decided": dict(decided) if decided else {},
            "leads_by_stage": {r["stage"]: r["n"] for r in stages},
            "posts_published": await p.fetchval(
                "SELECT count(*) FROM content_calendar WHERE status = 'posted' AND publish_at >= $1", since),
            "posts_upcoming": await p.fetchval(
                "SELECT count(*) FROM content_calendar WHERE status = 'approved' AND publish_at > now()"),
            "spend_month_usd": round(await self.month_spend(), 4),
        }

    async def save_metrics(self, day: date, data: dict[str, Any]) -> None:
        await self.p.execute(
            """INSERT INTO metrics (day, data) VALUES ($1, $2)
               ON CONFLICT (day) DO UPDATE SET data = EXCLUDED.data""",
            day, data,
        )
