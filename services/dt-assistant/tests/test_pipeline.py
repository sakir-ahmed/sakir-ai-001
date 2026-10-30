"""
End-to-end pipeline tests against a real Postgres, with every external API
mocked (OpenRouter, Meta Graph, Telegram, stt, Qdrant).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
import respx

from app.config import load_secrets, load_settings
from app.db import Database
from app.knowledge import Knowledge
from app.llm import LLM
from app.meta import GraphClient, InboundEvent
from app.pipeline import Assistant
from app.telegram import SalesDesk

DB_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="TEST_DATABASE_URL not set")
GRAPH = "https://graph.facebook.com/v25.0"
TG = "https://api.telegram.org/bot123:abc"


class Env:
    """Holds the assistant plus the mocked API routes and what they received."""
    def __init__(self) -> None:
        self.classification: dict = {"intent": "price", "language": "banglish", "confidence": 0.95}
        self.draft = "Apnar jonno amader Basic package ache. Demo dekhte chaile phone number din."
        self.telegram_texts: list[str] = []
        self.llm_calls: list[str] = []
        self._tg_id = 100

    def openrouter(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.llm_calls.append(body["model"])
        content = json.dumps(self.classification) if body.get("response_format") else self.draft
        return httpx.Response(200, json={
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 100, "cost": 0 if body["model"] == "openrouter/free" else 0.0004},
        })

    def telegram(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        if request.url.path.endswith("/sendMessage"):
            self.telegram_texts.append(body["text"])
        self._tg_id += 1
        return httpx.Response(200, json={"ok": True, "result": {"message_id": self._tg_id}})


@pytest_asyncio.fixture
async def env():
    db = Database(DB_URL)
    await db.connect()
    await db.p.execute("TRUNCATE leads, messages, approvals, content_calendar, spend, settings, metrics "
                       "RESTART IDENTITY CASCADE")
    e = Env()
    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://openrouter.ai/api/v1/chat/completions").mock(side_effect=e.openrouter)
        e.send = mock.post(f"{GRAPH}/PAGE1/messages").mock(
            return_value=httpx.Response(200, json={"message_id": "mid.out"}))
        e.comment_reply = mock.post(url__regex=rf"{GRAPH}/c\d+/comments").mock(
            return_value=httpx.Response(200, json={"id": "reply1"}))
        e.hide = mock.post(url__regex=rf"{GRAPH}/c\d+(\?|$)").mock(
            return_value=httpx.Response(200, json={"success": True}))
        mock.post(url__regex=rf"{TG}/.*").mock(side_effect=e.telegram)
        mock.post("http://stt:8000/embed").mock(return_value=httpx.Response(200, json={"vector": [0.1] * 384}))
        mock.post("http://qdrant:6333/collections/restora/points/search").mock(
            return_value=httpx.Response(200, json={"result": [
                {"payload": {"file": "products/dt-restora/pricing.md", "heading": "Packages",
                             "text": "Basic ৳ 1,500/month"}}]}))

        secrets, settings = load_secrets(), load_settings()
        desk = SalesDesk(secrets.sales_bot_token, secrets.owner_id)
        e.settings = settings
        e.db = db
        e.assistant = Assistant(secrets, settings, db,
                                LLM(secrets.openrouter_key, settings, db, notify=desk.send),
                                GraphClient("PAGE1", "page-token", "v25.0"),
                                Knowledge("http://stt:8000", "http://qdrant:6333", "restora"),
                                desk)
        yield e
    await db.close()


def dm(mid: str, text: str, user: str = "U1") -> InboundEvent:
    return InboundEvent(meta_id=mid, channel="messenger", user_id=user, user_name=None,
                        text=text, target_id=user)


async def test_price_question_becomes_draft_card(env):
    await env.assistant.handle_event(dm("m1", "bhai dam koto?"))
    approval = await env.db.p.fetchrow("SELECT * FROM approvals")
    assert approval["status"] == "waiting" and approval["intent"] == "price"
    assert approval["draft"] == env.draft
    assert not env.send.called                                  # nothing sent to the customer
    assert "Draft reply" in env.telegram_texts[-1] and "#1" in env.telegram_texts[-1]
    assert "pricing.md still has TODOs" in env.telegram_texts[-1]
    lead = await env.db.p.fetchrow("SELECT * FROM leads")
    assert lead["stage"] == "interested" and lead["language"] == "banglish"
    assert float(await env.db.month_spend()) == 0   # free classify + draft


async def test_approve_sends_and_logs(env):
    await env.assistant.handle_event(dm("m1", "bhai dam koto?"))
    result = await env.assistant.on_button("approve", 1)
    assert "SENT" in result and env.send.called
    sent = json.loads(env.send.calls.last.request.content)
    assert sent["recipient"]["id"] == "U1" and sent["messaging_type"] == "RESPONSE"
    assert (await env.db.get_approval(1))["status"] == "sent"
    assert await env.db.p.fetchval("SELECT how FROM messages WHERE direction = 'out'") == "approved"
    # A second tap must not send twice.
    assert "Already" in await env.assistant.on_button("approve", 1)
    assert env.send.call_count == 1


async def test_edit_flow(env):
    await env.assistant.handle_event(dm("m1", "bhai dam koto?"))
    assert "Waiting" in await env.assistant.on_button("edit", 1)
    result = await env.assistant.on_text("Sakir bhai apnake call korben.")
    assert "SENT (edited)" in result
    approval = await env.db.get_approval(1)
    assert approval["edited"] and approval["sent_text"] == "Sakir bhai apnake call korben."


async def test_duplicate_events_are_ignored(env):
    await env.assistant.handle_event(dm("m1", "price?"))
    await env.assistant.handle_event(dm("m1", "price?"))
    assert await env.db.p.fetchval("SELECT count(*) FROM messages") == 1
    assert await env.db.p.fetchval("SELECT count(*) FROM approvals") == 1


async def test_spam_comment_is_hidden(env):
    env.classification = {"intent": "spam", "language": "en", "confidence": 0.99}
    ev = InboundEvent(meta_id="c11", channel="comment", user_id="U5", user_name="Bot",
                      text="Buy followers http://x", target_id="c11", post_id="p1")
    await env.assistant.handle_event(ev)
    assert env.hide.called
    assert await env.db.p.fetchval("SELECT count(*) FROM approvals") == 0


async def test_complaint_gets_holding_reply_and_escalation(env):
    env.classification = {"intent": "complaint", "language": "en", "confidence": 0.9}
    await env.assistant.handle_event(dm("m1", "Your software stopped working, very bad service!"))
    held = json.loads(env.send.calls.last.request.content)["message"]["text"]
    assert held == env.settings.holding_reply("en")
    approval = await env.db.p.fetchrow("SELECT * FROM approvals")
    assert approval["kind"] == "escalation" and approval["status"] == "waiting"
    assert "deepseek/deepseek-v3.2" in env.llm_calls                    # premium model for escalations


async def test_paused_uses_no_model(env):
    await env.db.set_setting("paused", True)
    await env.assistant.handle_event(dm("m1", "dam koto?"))
    assert env.llm_calls == []
    assert env.send.called                                              # holding reply
    assert (await env.db.p.fetchrow("SELECT kind FROM approvals"))["kind"] == "escalation"


async def test_paid_budget_reached_still_allows_free_drafts(env):
    await env.db.add_spend("reply", 30.0, 0, 0)
    await env.assistant.handle_event(dm("m1", "dam koto?"))
    assert env.llm_calls == ["openrouter/free", "openrouter/free"]
    assert not env.send.called
    assert (await env.db.p.fetchrow("SELECT status FROM approvals"))["status"] == "waiting"


async def test_template_auto_send_when_allowed(env):
    env.settings.raw["autonomy"]["auto_send_templates"] = True
    env.classification = {"intent": "faq", "language": "en", "confidence": 0.95, "faq_key": "mobile_app"}
    await env.assistant.handle_event(dm("m1", "Do you have a mobile app?"))
    text = json.loads(env.send.calls.last.request.content)["message"]["text"]
    assert "web application and a mobile app" in text
    assert await env.db.p.fetchval("SELECT count(*) FROM approvals") == 0
    env.settings.raw["autonomy"]["auto_send_templates"] = False


async def test_todo_templates_are_ignored(env):
    assert "office_hours" not in env.assistant.kb.templates()
    assert "mobile_app" in env.assistant.kb.templates()


async def test_approval_after_window_expires(env):
    await env.assistant.handle_event(dm("m1", "dam koto?"))
    await env.db.p.execute("UPDATE leads SET last_inbound_at = $1",
                           datetime.now(timezone.utc) - timedelta(hours=30))
    result = await env.assistant.on_button("approve", 1)
    assert "NOT sent" in result and "24-hour" in result
    assert (await env.db.get_approval(1))["status"] == "expired"
    assert not env.send.called


async def test_comment_reply_goes_under_comment(env):
    env.classification = {"intent": "demo", "language": "en", "confidence": 0.9}
    ev = InboundEvent(meta_id="c21", channel="comment", user_id="U6", user_name="Karim",
                      text="Can I see a demo?", target_id="c21", post_id="p1")
    await env.assistant.handle_event(ev)
    await env.assistant.on_button("approve", 1)
    assert env.comment_reply.called
    lead = await env.db.p.fetchrow("SELECT * FROM leads")
    assert lead["name"] == "Karim" and lead["stage"] == "demo"


async def test_followup_drafted_for_quiet_warm_lead(env):
    await env.assistant.handle_event(dm("m1", "dam koto?"))
    await env.assistant.on_button("approve", 1)
    now = datetime.now(timezone.utc)
    await env.db.p.execute("UPDATE leads SET last_inbound_at = $1, last_outbound_at = $2",
                           now - timedelta(hours=21), now - timedelta(hours=20, minutes=30))
    await env.assistant.followup_tick()
    approval = await env.db.p.fetchrow("SELECT * FROM approvals WHERE kind = 'followup'")
    assert approval is not None and approval["status"] == "waiting"
    await env.assistant.followup_tick()                                  # no duplicate
    assert await env.db.p.fetchval("SELECT count(*) FROM approvals WHERE kind = 'followup'") == 1


async def test_summary_and_commands(env):
    await env.assistant.handle_event(dm("m1", "dam koto?"))
    summary = await env.db.summary(1)
    assert summary["messages_in"] == 1 and summary["approvals_waiting"] == 1
    assert "Messages in: 1" in await env.assistant.on_command("stats", "")
    assert "Paused" in await env.assistant.on_command("pause", "")
    assert await env.db.get_setting("paused") is True


async def test_retention_removes_only_old_data(env):
    await env.assistant.handle_event(dm("m1", "dam koto?", user="OLD"))
    await env.assistant.on_button("reject", 1)
    await env.assistant.handle_event(dm("m2", "demo chai", user="NEW"))
    old = datetime.now(timezone.utc) - timedelta(days=400)
    await env.db.p.execute("UPDATE messages SET created_at = $1 WHERE meta_id = 'm1'", old)
    await env.db.p.execute("UPDATE approvals SET decided_at = $1 WHERE id = 1", old)
    await env.db.p.execute("UPDATE leads SET stage = 'lost', last_inbound_at = $1 WHERE channel_user_id = 'OLD'", old)
    await env.assistant.retention_tick()
    assert await env.db.p.fetchval("SELECT count(*) FROM leads") == 1          # NEW kept
    assert await env.db.p.fetchval("SELECT count(*) FROM messages WHERE meta_id = 'm2'") == 1
    assert await env.db.p.fetchval("SELECT count(*) FROM approvals WHERE status = 'waiting'") == 1
    removed = await env.db.purge_old(0, 0, 0)                                  # 0 = keep forever
    assert removed == {"messages": 0, "approvals": 0, "leads": 0}

