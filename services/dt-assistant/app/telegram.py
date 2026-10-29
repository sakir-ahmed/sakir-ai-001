"""
@DTSalesDesk_bot — the approval desk for customer replies.

Only Sakir's Telegram user ID is served; messages from anyone else are
ignored. Uses long polling (no public webhook needed).

Buttons on every draft card:  Approve | Edit | Reject
Commands:
  /inbox         drafts waiting, oldest first (re-sends their cards)
  /stats         today's numbers
  /lead <text>   find a lead by name, business or phone
  /pause         stop automatic replies (customers get a holding reply)
  /resume        start automatic replies again
  /cancel        cancel an edit in progress
  /help          this list
While an edit is in progress, the next plain text message becomes the reply.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Protocol

import httpx

log = logging.getLogger("dt.telegram")
TEXT_LIMIT = 4000   # Telegram's hard limit is 4096


class DeskHandler(Protocol):
    async def on_button(self, action: str, approval_id: int) -> str: ...
    async def on_text(self, text: str) -> str | None: ...
    async def on_command(self, command: str, arg: str) -> str: ...


class SalesDesk:
    def __init__(self, token: str, owner_id: str) -> None:
        self.token = token
        self.owner_id = str(owner_id)
        self.api = f"https://api.telegram.org/bot{token}"
        self.http = httpx.AsyncClient(timeout=45)

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.owner_id)

    async def close(self) -> None:
        await self.http.aclose()

    async def _call(self, method: str, **payload: Any) -> dict[str, Any]:
        r = await self.http.post(f"{self.api}/{method}", json=payload)
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"telegram {method}: {data.get('description')}")
        return data["result"]

    # ---- outgoing ----------------------------------------------------------------
    async def send(self, text: str, buttons: list[list[tuple[str, str]]] | None = None) -> int | None:
        """Send plain text to Sakir. buttons: rows of (label, callback_data)."""
        if not self.enabled:
            log.warning("sales desk bot not configured; message dropped: %s", text[:80])
            return None
        payload: dict[str, Any] = {"chat_id": self.owner_id, "text": text[:TEXT_LIMIT],
                                   "disable_web_page_preview": True}
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": [
                [{"text": label, "callback_data": data} for label, data in row] for row in buttons]}
        try:
            result = await self._call("sendMessage", **payload)
            return int(result["message_id"])
        except Exception as exc:
            log.error("telegram send failed: %s", exc)
            return None

    async def edit(self, message_id: int, text: str) -> None:
        """Replace a card's text and remove its buttons."""
        try:
            await self._call("editMessageText", chat_id=self.owner_id, message_id=message_id,
                             text=text[:TEXT_LIMIT], disable_web_page_preview=True)
        except Exception as exc:
            log.warning("telegram edit failed: %s", exc)

    async def send_document(self, path: Path, caption: str) -> None:
        if not self.enabled:
            return
        with path.open("rb") as fh:
            r = await self.http.post(f"{self.api}/sendDocument",
                                     data={"chat_id": self.owner_id, "caption": caption[:1000]},
                                     files={"document": (path.name, fh)}, timeout=120)
        if not r.json().get("ok"):
            log.error("telegram sendDocument failed: %s", r.text[:200])

    # ---- incoming (long polling) ----------------------------------------------------
    async def run(self, handler: DeskHandler) -> None:
        if not self.enabled:
            log.warning("SALES_BOT_TOKEN or TELEGRAM_OWNER_ID missing; approval desk is off")
            return
        await self._set_commands()
        offset = 0
        while True:
            try:
                updates = await self._call("getUpdates", offset=offset, timeout=30,
                                           allowed_updates=["message", "callback_query"])
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("getUpdates failed: %s; retrying in 5s", exc)
                await asyncio.sleep(5)
                continue
            for upd in updates:
                offset = max(offset, upd["update_id"] + 1)
                try:
                    await self._dispatch(upd, handler)
                except Exception:
                    log.exception("error handling telegram update")

    async def _dispatch(self, upd: dict[str, Any], handler: DeskHandler) -> None:
        if "callback_query" in upd:
            cq = upd["callback_query"]
            if str(cq.get("from", {}).get("id")) != self.owner_id:
                return
            action, _, raw_id = (cq.get("data") or "").partition(":")
            reply = "Unknown button"
            if raw_id.isdigit() and action in {"approve", "edit", "reject"}:
                reply = await handler.on_button(action, int(raw_id))
            await self._call("answerCallbackQuery", callback_query_id=cq["id"], text=reply[:190])
            return

        msg = upd.get("message") or {}
        if str((msg.get("from") or {}).get("id")) != self.owner_id:
            return                                           # strangers are ignored silently
        text = (msg.get("text") or "").strip()
        if not text:
            return
        if text.startswith("/"):
            command, _, arg = text[1:].partition(" ")
            answer = await handler.on_command(command.split("@")[0].lower(), arg.strip())
        else:
            answer = await handler.on_text(text)
        if answer:
            await self.send(answer)

    async def _set_commands(self) -> None:
        commands = [
            ("inbox", "Drafts waiting for approval"),
            ("stats", "Today's numbers"),
            ("lead", "Find a lead: /lead <name or phone>"),
            ("pause", "Stop automatic replies"),
            ("resume", "Start automatic replies"),
            ("cancel", "Cancel the edit in progress"),
            ("help", "Commands"),
        ]
        try:
            await self._call("setMyCommands", commands=[{"command": c, "description": d} for c, d in commands])
        except Exception as exc:
            log.warning("setMyCommands failed: %s", exc)
