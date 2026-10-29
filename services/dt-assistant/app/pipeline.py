"""
The sales pipeline and the approval desk logic.

Inbound flow (one Facebook/Instagram event):
  1. dedupe by Meta id, upsert the lead, store the message
  2. voice message -> transcribe with the stt service
  3. classify intent + language (cheap model) unless paused / over budget
  4. policy.decide() -> hide | holding | escalate | template | draft
  5. send automatically, or post a draft card to @DTSalesDesk_bot
  6. every outbound message is logged; Messenger replies respect the 24h window

Scheduled jobs (started from main.py):
  followup_tick   one follow-up draft for warm leads that went quiet
  stale_tick      warn about old drafts; expire drafts whose window closed
  publisher_tick  publish approved posts from content_calendar
  metrics_tick    daily snapshot for Hermes' evening summary
  retention_tick  daily deletion of old messages, drafts and dead leads
"""
from __future__ import annotations

import logging
import secrets as pysecrets
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import policy
from .config import LOCAL_TZ, OUTBOX_DIR, Secrets, Settings
from .db import Database
from .knowledge import Knowledge
from .llm import LLM, BudgetExceeded, LLMError, parse_json
from .meta import GraphClient, GraphError, InboundEvent
from .telegram import SalesDesk

log = logging.getLogger("dt.pipeline")

LANGUAGE_NAMES = {"bn": "Bangla (Bengali script)", "banglish": "Banglish (Bangla written in English letters)",
                  "en": "English"}
CHANNEL_NAMES = {"messenger": "Messenger", "instagram": "Instagram DM", "comment": "Facebook comment"}

FALLBACK_CLASSIFY_PROMPT = (
    "Classify the customer message for a software company. Return ONLY JSON with keys: "
    "intent (one of {intents}), language (bn|banglish|en), confidence (0-1), faq_key (one of "
    "{faq_keys} or null), name, business, phone (null when not mentioned)."
)
FALLBACK_REPLY_PROMPT = (
    "You are {assistant_name} for {company}. Reply in {language_name}. Be short and warm. "
    "Use only facts from CONTEXT; if missing, say Sakir will confirm and ask for a phone number. "
    "Never give discounts or promise dates. CONTEXT:\n{context}\nHISTORY:\n{history}"
)
HOLDING_REPEAT = timedelta(hours=12)


class Assistant:
    def __init__(self, secrets: Secrets, settings: Settings, db: Database, llm: LLM,
                 graph: GraphClient, knowledge: Knowledge, desk: SalesDesk) -> None:
        self.secrets = secrets
        self.settings = settings
        self.db = db
        self.llm = llm
        self.graph = graph
        self.kb = knowledge
        self.desk = desk
        self._last_metrics_day: str | None = None

    # =========================================================================
    # Inbound
    # =========================================================================
    async def handle_event(self, ev: InboundEvent) -> None:
        if await self.db.message_seen(ev.meta_id):
            return
        lead = await self.db.upsert_lead(ev.user_id, ev.channel, ev.user_name, self.settings.product)

        text, voice_failed = ev.text, False
        if ev.audio_url:
            try:
                audio = await self.graph.download(ev.audio_url)
                spoken = await self.kb.transcribe(audio)
                text = f"{text}\n{spoken}".strip() if spoken else text
                voice_failed = not spoken
            except Exception as exc:
                log.warning("voice transcription failed: %s", exc)
                voice_failed = True
            if voice_failed and not text:
                text = "[voice message — could not transcribe]"

        message_id = await self.db.add_message(lead["id"], ev.channel, "in", text,
                                               meta_id=ev.meta_id, target_id=ev.post_id)
        if message_id is None:          # another worker stored it first
            return

        paused = bool(await self.db.get_setting("paused", False))
        over_budget = (not self.llm.configured) or await self.llm.over_budget()
        cls = await self._classify(text) if not (paused or over_budget or voice_failed) else self._heuristic(text)
        await self.db.set_message_analysis(message_id, cls["intent"], cls["language"], cls["confidence"])
        await self.db.update_lead(
            lead["id"], name=cls["name"], business=cls["business"], phone=cls["phone"],
            language=cls["language"], stage=policy.next_stage(lead["stage"], cls["intent"]),
        )

        has_template = cls["faq_key"] is not None
        decision = policy.decide(cls["intent"], cls["confidence"], has_template,
                                 self.settings.get("autonomy", default={}) or {}, paused, over_budget)
        if voice_failed and decision.auto_send and decision.action != "hide":
            decision = policy.Decision(decision.action, False, "voice message could not be transcribed")
        log.info("lead=%s intent=%s lang=%s conf=%.2f -> %s (%s)", lead["id"], cls["intent"],
                 cls["language"], cls["confidence"], decision.action, decision.reason)

        await self._act(decision, ev, lead["id"], message_id, text, cls)

    async def _act(self, decision: policy.Decision, ev: InboundEvent, lead_id: int,
                   message_id: int, text: str, cls: dict[str, Any]) -> None:
        lang = cls["language"]

        if decision.action == "hide":
            if ev.channel == "comment" and self.settings.get("meta", "hide_spam_comments", default=True):
                try:
                    await self.graph.hide_comment(ev.target_id)
                except GraphError as exc:
                    log.warning("could not hide spam comment: %s", exc)
            return

        if decision.action == "holding":
            await self._send_holding(ev, lead_id, lang)
            await self._card(lead_id, message_id, "escalation", ev.channel, ev.target_id, cls, text,
                             draft=self.settings.holding_reply(lang),
                             note=f"No AI draft ({decision.reason}). Tap Edit to answer personally.")
            return

        if decision.action == "escalate":
            await self._send_holding(ev, lead_id, lang)
            draft = await self._safe_draft(lead_id, text, cls, purpose="reply_premium")
            await self._card(lead_id, message_id, "escalation", ev.channel, ev.target_id, cls, text, draft,
                             note=f"{cls['intent'].upper()}: a holding reply was sent; this needs you.")
            return

        if decision.action == "template":
            template = self.kb.templates()[cls["faq_key"]]
            reply = policy.render_template(template, lang, {"assistant_name": self.settings.assistant_name})
        else:
            purpose = "reply_premium" if await self._lead_stage(lead_id) == "proposal" else "reply"
            reply = await self._safe_draft(lead_id, text, cls, purpose=purpose)

        if decision.auto_send and reply:
            ok, error = await self.deliver(ev.channel, ev.target_id, lead_id, reply,
                                           how="template" if decision.action == "template" else "auto")
            if ok:
                return
            log.warning("auto-send failed (%s); falling back to a draft card", error)
        note = decision.reason
        if cls["intent"] == "price" and not self.kb.pricing_ready():
            note += " | pricing.md still has TODOs — check the price"
        await self._card(lead_id, message_id, "reply", ev.channel, ev.target_id, cls, text, reply, note=note)

    async def _lead_stage(self, lead_id: int) -> str:
        lead = await self.db.get_lead(lead_id)
        return lead["stage"] if lead else "new"

    # ---- classification ---------------------------------------------------------
    def _heuristic(self, text: str) -> dict[str, Any]:
        return policy.normalise_classification({"intent": "other", "confidence": 0}, text, set())

    async def _classify(self, text: str) -> dict[str, Any]:
        templates = self.kb.templates()
        faq_keys = sorted(templates)
        faq_list = "\n".join(f"- {k}: {v.get('question', '')}" for k, v in templates.items()) or "(none)"
        prompt = self.kb.classify_prompt() or FALLBACK_CLASSIFY_PROMPT
        prompt = (prompt.replace("{intents}", ", ".join(policy.INTENTS))
                        .replace("{faq_keys}", ", ".join(faq_keys) or "none")
                        .replace("{faq_list}", faq_list))
        try:
            raw = await self.llm.chat("classify", [{"role": "system", "content": prompt},
                                                   {"role": "user", "content": text[:2000]}],
                                      json_mode=True, max_tokens=200, temperature=0)
            return policy.normalise_classification(parse_json(raw), text, set(faq_keys))
        except (LLMError, BudgetExceeded, ValueError) as exc:
            log.warning("classification failed, using heuristic: %s", exc)
            return self._heuristic(text)

    # ---- drafting ------------------------------------------------------------------
    async def _safe_draft(self, lead_id: int, text: str, cls: dict[str, Any], purpose: str) -> str:
        try:
            return await self.draft_reply(lead_id, text, cls, purpose)
        except (LLMError, BudgetExceeded) as exc:
            log.warning("draft failed: %s", exc)
            return self.settings.holding_reply(cls["language"])

    async def draft_reply(self, lead_id: int, text: str, cls: dict[str, Any], purpose: str = "reply") -> str:
        chunks = await self.kb.search(text)
        context = "\n\n".join(f"[{c.get('file', '')} — {c.get('heading', '')}]\n{c.get('text', '')}"
                              for c in chunks) or "(no matching facts found)"
        history = await self.db.history(lead_id, limit=6)
        history_text = "\n".join(f"{'Customer' if h['direction'] == 'in' else 'Us'}: {h['text']}"
                                 for h in history[:-1]) or "(first message)"
        lead = await self.db.get_lead(lead_id)
        values = {
            "assistant_name": self.settings.assistant_name,
            "company": self.settings.company,
            "language_name": LANGUAGE_NAMES.get(cls["language"], "English"),
            "language": cls["language"],
            "context": context,
            "history": history_text,
            "customer_message": text,
            "lead_name": (lead["name"] if lead and lead["name"] else "the customer"),
            "intent": cls["intent"],
        }
        prompt = self.kb.reply_prompt() or FALLBACK_REPLY_PROMPT
        for key, value in values.items():
            prompt = prompt.replace("{" + key + "}", str(value))
        reply = await self.llm.chat(purpose, [{"role": "system", "content": prompt},
                                              {"role": "user", "content": text[:2000]}],
                                    max_tokens=400, temperature=0.4)
        return reply.strip().strip('"').strip()

    # =========================================================================
    # Delivery
    # =========================================================================
    async def deliver(self, channel: str, target_id: str, lead_id: int, text: str, how: str) -> tuple[bool, str]:
        """Send a reply to the customer. Returns (ok, error)."""
        if not self.secrets.meta_ready:
            return False, "Meta is not configured (META_* secrets missing)"
        lead = await self.db.get_lead(lead_id)
        try:
            if channel in ("messenger", "instagram"):
                if not policy.inside_window(lead["last_inbound_at"], self.settings.window_hours):
                    return False, "outside Meta's 24-hour reply window"
                meta_id = await self.graph.send_message(target_id, text)
            elif channel == "comment":
                meta_id = await self.graph.reply_comment(target_id, text)
            else:
                return False, f"unknown channel {channel}"
        except GraphError as exc:
            if exc.outside_window:
                return False, "outside Meta's 24-hour reply window"
            return False, str(exc)
        await self.db.add_message(lead_id, channel, "out", text, meta_id=meta_id or None, how=how,
                                  target_id=target_id)
        await self.db.update_lead(lead_id, last_outbound_at=datetime.now(timezone.utc))
        return True, ""

    async def _send_holding(self, ev: InboundEvent, lead_id: int, language: str) -> None:
        """At most one holding reply per lead every 12 hours."""
        lead = await self.db.get_lead(lead_id)
        last = lead["holding_sent_at"] if lead else None
        if last and datetime.now(timezone.utc) - last < HOLDING_REPEAT:
            return
        ok, error = await self.deliver(ev.channel, ev.target_id, lead_id,
                                       self.settings.holding_reply(language), how="holding")
        if ok:
            await self.db.update_lead(lead_id, holding_sent_at=datetime.now(timezone.utc))
        else:
            log.warning("holding reply not sent: %s", error)

    # =========================================================================
    # Approval desk (DeskHandler)
    # =========================================================================
    async def _card(self, lead_id: int, inbound_message_id: int | None, kind: str, channel: str,
                    target_id: str, cls: dict[str, Any], customer_text: str, draft: str, note: str = "") -> None:
        approval_id = await self.db.create_approval(lead_id, inbound_message_id, kind, channel,
                                                    target_id, cls.get("intent"), draft)
        lead = await self.db.get_lead(lead_id)
        who = " — ".join(x for x in (lead["name"], lead["business"], lead["phone"]) if x) or "unknown"
        text = (
            f"#{approval_id} · {CHANNEL_NAMES.get(channel, channel)} · {cls.get('language', '?')} · "
            f"{cls.get('intent', '?')} ({cls.get('confidence', 0):.0%})\n"
            f"From: {who} · stage: {lead['stage']}\n"
            f"Customer: {policy.truncate(customer_text, 1200)}\n\n"
            f"Draft reply:\n{policy.truncate(draft, 1800)}"
            + (f"\n\nNote: {note}" if note else "")
        )
        message_id = await self.desk.send(text, buttons=[[("Approve", f"approve:{approval_id}"),
                                                          ("Edit", f"edit:{approval_id}"),
                                                          ("Reject", f"reject:{approval_id}")]])
        if message_id:
            await self.db.set_approval_telegram_id(approval_id, message_id)

    async def _send_approved(self, approval_id: int, text: str, edited: bool) -> str:
        rec = await self.db.claim_approval(approval_id)
        if rec is None:
            return f"#{approval_id} was already handled"
        ok, error = await self.deliver(rec["channel"], rec["target_id"], rec["lead_id"], text,
                                       how="edited" if edited else "approved")
        if ok:
            await self.db.finish_approval(approval_id, "sent", sent_text=text, edited=edited)
            result = f"#{approval_id} SENT{' (edited)' if edited else ''}"
        else:
            status = "expired" if "window" in error else "failed"
            await self.db.finish_approval(approval_id, status, edited=edited, error=error)
            lead = await self.db.get_lead(rec["lead_id"])
            phone = f" Phone: {lead['phone']}." if lead and lead["phone"] else ""
            result = f"#{approval_id} NOT sent: {error}.{phone}"
        if rec["telegram_message_id"]:
            await self.desk.edit(rec["telegram_message_id"], f"{result}\n\n{policy.truncate(text, 1500)}")
        return result

    async def on_button(self, action: str, approval_id: int) -> str:
        rec = await self.db.get_approval(approval_id)
        if rec is None:
            return "Unknown draft"
        if rec["status"] != "waiting":
            return f"Already {rec['status']}"
        if action == "approve":
            return await self._send_approved(approval_id, rec["draft"], edited=False)
        if action == "reject":
            if await self.db.claim_approval(approval_id):
                await self.db.finish_approval(approval_id, "rejected")
                if rec["telegram_message_id"]:
                    await self.desk.edit(rec["telegram_message_id"],
                                         f"#{approval_id} REJECTED (nothing sent)\n\n{policy.truncate(rec['draft'], 800)}")
            return f"#{approval_id} rejected"
        if action == "edit":
            await self.db.set_setting("edit_waiting", approval_id)
            await self.desk.send(f"Send the reply text for #{approval_id} now (or /cancel).")
            return "Waiting for your text"
        return "Unknown action"

    async def on_text(self, text: str) -> str | None:
        approval_id = await self.db.get_setting("edit_waiting")
        if not approval_id:
            return "Use the buttons on a draft, or /help."
        await self.db.set_setting("edit_waiting", None)
        return await self._send_approved(int(approval_id), text, edited=True)

    async def on_command(self, command: str, arg: str) -> str:
        if command in ("start", "help"):
            return ("Datatech BD sales desk\n/inbox — drafts waiting\n/stats — today\n/lead <text> — find a lead\n"
                    "/pause — stop automatic replies\n/resume — restart them\n/cancel — cancel an edit")
        if command == "inbox":
            waiting = await self.db.waiting_approvals()
            if not waiting:
                return "Inbox empty — no drafts waiting."
            for rec in waiting[:10]:
                await self.desk.send(
                    f"#{rec['id']} · {CHANNEL_NAMES.get(rec['channel'], rec['channel'])} · {rec['intent']}\n"
                    f"{rec['lead_name'] or 'unknown'}\n\nDraft:\n{policy.truncate(rec['draft'], 1500)}",
                    buttons=[[("Approve", f"approve:{rec['id']}"), ("Edit", f"edit:{rec['id']}"),
                              ("Reject", f"reject:{rec['id']}")]])
            return f"{len(waiting)} draft(s) waiting" + (" (showing 10)" if len(waiting) > 10 else "")
        if command == "stats":
            s = await self.db.summary(1)
            return (f"Last 24 hours\nNew leads: {s['new_leads']}\nMessages in: {s['messages_in']}\n"
                    f"Replies out: {s['replies_out']}\nWaiting drafts: {s['approvals_waiting']}\n"
                    f"Decided: {s['approvals_decided']}\nStages: {s['leads_by_stage']}\n"
                    f"Spend this month: ${s['spend_month_usd']:.2f}")
        if command == "lead":
            rows = await self.db.search_leads(arg, limit=5)
            if not rows:
                return "No lead found."
            blocks = []
            for r in rows:
                last = (r["last_inbound_at"].astimezone(LOCAL_TZ).strftime("%d %b %H:%M")
                        if r["last_inbound_at"] else "-")
                blocks.append(f"{r['name'] or 'unknown'} · {r['business'] or '-'} · {r['phone'] or '-'}\n"
                              f"stage {r['stage']} · {r['source']} · last message {last}")
            return "\n\n".join(blocks)
        if command == "pause":
            await self.db.set_setting("paused", True)
            return "Paused. Customers get a holding reply; every message comes here as a card."
        if command == "resume":
            await self.db.set_setting("paused", False)
            return "Resumed."
        if command == "cancel":
            await self.db.set_setting("edit_waiting", None)
            return "Edit cancelled."
        return "Unknown command. /help"

    # =========================================================================
    # Scheduled jobs
    # =========================================================================
    async def followup_tick(self) -> None:
        cfg = self.settings.get("followup", default={}) or {}
        if not cfg.get("enabled", True) or not self.llm.configured:
            return
        leads = await self.db.followup_candidates(cfg.get("stages", ["interested", "demo"]),
                                                  float(cfg.get("after_silence_hours", 20)),
                                                  self.settings.window_hours)
        for lead in leads:
            history = await self.db.history(lead["id"], limit=6)
            convo = "\n".join(f"{'Customer' if h['direction'] == 'in' else 'Us'}: {h['text']}" for h in history)
            lang = lead["language"] or "en"
            try:
                draft = await self.llm.chat("followup", [
                    {"role": "system", "content":
                        f"You are {self.settings.assistant_name} for {self.settings.company}. Write ONE short, "
                        f"friendly follow-up in {LANGUAGE_NAMES.get(lang, 'English')} for this conversation. "
                        "Offer a free demo or ask one helpful question. No pressure, no discounts, max 2 sentences."},
                    {"role": "user", "content": convo[-3000:]}], max_tokens=150, temperature=0.5)
            except (LLMError, BudgetExceeded) as exc:
                log.warning("follow-up draft failed: %s", exc)
                return
            await self.db.update_lead(lead["id"], followup_sent_at=datetime.now(timezone.utc))
            cls = {"intent": "followup", "language": lang, "confidence": 1.0}
            await self._card(lead["id"], None, "followup", lead["source"], lead["channel_user_id"], cls,
                             history[-1]["text"] if history else "", draft,
                             note="Follow-up: the customer went quiet. Approve before the 24-hour window closes.")

    async def stale_tick(self) -> None:
        stale_h = float(self.settings.get("meta", "draft_stale_hours", default=23))
        for rec in await self.db.stale_approvals(stale_h):
            await self.db.mark_stale_notified(rec["id"])
            await self.desk.send(f"Draft #{rec['id']} is {stale_h:.0f}h old. Messenger replies stop working "
                                 f"24h after the customer's last message. /inbox")

    async def publisher_tick(self) -> None:
        auto = set(self.settings.get("publisher", "auto_platforms", default=["facebook", "instagram"]) or [])
        for post in await self.db.due_posts():
            media = self._media_path(post["media_path"])
            try:
                if post["platform"] == "facebook" and "facebook" in auto and self.secrets.meta_ready:
                    result = await self.graph.post_facebook(post["caption"], media)
                    await self.db.set_post_status(post["id"], "posted", f"facebook id {result}")
                elif post["platform"] == "instagram" and "instagram" in auto and self.secrets.ig_user_id:
                    if not media:
                        raise GraphError("Instagram needs an image (media_path)")
                    url = self._publish_media(media)
                    result = await self.graph.post_instagram(post["caption"], url)
                    await self.db.set_post_status(post["id"], "posted", f"instagram id {result}")
                else:
                    await self._remind(post, media)
                    await self.db.set_post_status(post["id"], "reminded", "sent to Sakir to post manually")
            except Exception as exc:
                log.error("publishing post %s failed: %s", post["id"], exc)
                await self.db.set_post_status(post["id"], "failed", str(exc))
                await self.desk.send(f"Post #{post['id']} ({post['platform']}) FAILED: {exc}")

    async def _remind(self, post: Any, media: Path | None) -> None:
        when = post["publish_at"].astimezone(LOCAL_TZ).strftime("%d %b %H:%M")
        await self.desk.send(f"Time to post on {post['platform'].upper()} ({when}), product {post['product']}.\n"
                             f"Caption (copy):\n\n{post['caption']}")
        if media:
            await self.desk.send_document(media, f"Media for post #{post['id']}")

    def _media_path(self, raw: str | None) -> Path | None:
        """Only files inside /outbox may be published."""
        if not raw:
            return None
        path = (OUTBOX_DIR / raw.removeprefix("/outbox/")).resolve()
        if OUTBOX_DIR.resolve() not in path.parents or not path.is_file():
            raise ValueError(f"media not found inside /outbox: {raw}")
        return path

    def _publish_media(self, media: Path) -> str:
        """Copy to outbox/public with an unguessable name; Nginx serves it for Instagram."""
        public = OUTBOX_DIR / "public"
        public.mkdir(exist_ok=True)
        name = f"{pysecrets.token_urlsafe(16)}{media.suffix.lower()}"
        shutil.copyfile(media, public / name)
        return f"{self.secrets.public_base_url}/public-media/{name}"

    async def metrics_tick(self) -> None:
        now = datetime.now(LOCAL_TZ)
        target = self.settings.get("daily_metrics_time", default="21:00")
        today = now.date().isoformat()
        if now.strftime("%H:%M") >= target and self._last_metrics_day != today:
            self._last_metrics_day = today
            await self.db.save_metrics(now.date(), await self.db.summary(1))
            log.info("daily metrics saved for %s", today)

    async def retention_tick(self) -> None:
        """Delete data older than the retention periods in dt-assistant.yaml."""
        cfg = self.settings.get("retention", default={}) or {}
        removed = await self.db.purge_old(int(cfg.get("messages_days", 365)),
                                          int(cfg.get("approvals_days", 180)),
                                          int(cfg.get("inactive_leads_days", 365)))
        if any(removed.values()):
            log.info("retention: removed %s", removed)
