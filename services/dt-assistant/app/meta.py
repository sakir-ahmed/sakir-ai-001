"""
Meta (Facebook/Instagram) integration: webhook verification and parsing,
and the Graph API calls the assistant needs.

Webhook events we handle
  * Messenger messages to the Page          object=page,      entry[].messaging[]
  * Instagram DMs                           object=instagram, entry[].messaging[]
  * New comments on Page posts              object=page,      entry[].changes[field=feed, item=comment, verb=add]

Graph API calls
  * send_message     POST /{page-id}/messages   (Messenger and Instagram DMs)
  * reply_comment    POST /{comment-id}/comments
  * hide_comment     POST /{comment-id}  is_hidden=true
  * post_facebook    POST /{page-id}/photos or /{page-id}/feed
  * post_instagram   POST /{ig-user-id}/media  then /media_publish
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("dt.meta")
GRAPH = "https://graph.facebook.com"
MESSENGER_TEXT_LIMIT = 2000


def verify_signature(app_secret: str, body: bytes, header: str | None) -> bool:
    """Check X-Hub-Signature-256 ('sha256=<hex hmac of raw body>')."""
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


@dataclass
class InboundEvent:
    meta_id: str               # message mid or comment id (used for dedupe)
    channel: str               # messenger | instagram | comment
    user_id: str               # PSID / IGSID / commenter id
    user_name: str | None
    text: str
    target_id: str             # where the reply goes: PSID/IGSID or comment id
    audio_url: str | None = None
    post_id: str | None = None


def parse_webhook(payload: dict[str, Any], page_id: str, ig_user_id: str = "") -> list[InboundEvent]:
    """Turn one webhook payload into zero or more events we should answer."""
    events: list[InboundEvent] = []
    obj = payload.get("object")
    if obj not in ("page", "instagram"):
        return events

    for entry in payload.get("entry", []) or []:
        # ---- direct messages ----
        for m in entry.get("messaging", []) or []:
            msg = m.get("message")
            sender = (m.get("sender") or {}).get("id", "")
            if not msg or msg.get("is_echo") or not sender:
                continue                                # echoes of our own replies, reads, etc.
            if sender in (page_id, ig_user_id):
                continue
            audio = next((a.get("payload", {}).get("url") for a in msg.get("attachments", []) or []
                          if a.get("type") == "audio"), None)
            text = (msg.get("text") or "").strip()
            if not text and not audio:
                continue                                # stickers, images without text
            channel = "instagram" if obj == "instagram" else "messenger"
            events.append(InboundEvent(
                meta_id=msg.get("mid", ""), channel=channel, user_id=sender, user_name=None,
                text=text, target_id=sender, audio_url=audio,
            ))

        # ---- comments on Page posts ----
        for change in entry.get("changes", []) or []:
            if change.get("field") != "feed":
                continue
            v = change.get("value") or {}
            if v.get("item") != "comment" or v.get("verb") != "add":
                continue
            frm = v.get("from") or {}
            if not frm.get("id") or frm.get("id") == page_id:
                continue                                # our own replies
            text = (v.get("message") or "").strip()
            if not text or not v.get("comment_id"):
                continue
            events.append(InboundEvent(
                meta_id=v["comment_id"], channel="comment", user_id=frm["id"],
                user_name=frm.get("name"), text=text, target_id=v["comment_id"], post_id=v.get("post_id"),
            ))
    return [e for e in events if e.meta_id]


class GraphClient:
    def __init__(self, page_id: str, page_token: str, version: str, ig_user_id: str = "") -> None:
        self.page_id = page_id
        self.token = page_token
        self.ig_user_id = ig_user_id
        self.base = f"{GRAPH}/{version}"
        self.http = httpx.AsyncClient(timeout=30)

    async def close(self) -> None:
        await self.http.aclose()

    async def _post(self, path: str, **kwargs: Any) -> dict[str, Any]:
        params = {"access_token": self.token}
        r = await self.http.post(f"{self.base}/{path}", params=params, **kwargs)
        data = r.json() if r.content else {}
        if r.status_code >= 400 or "error" in data:
            err = data.get("error", {})
            raise GraphError(f"{err.get('code', r.status_code)}: {err.get('message', r.text[:300])}",
                             code=err.get("code"), subcode=err.get("error_subcode"))
        return data

    async def send_message(self, recipient_id: str, text: str) -> str:
        """Reply in Messenger or Instagram DM (inside the 24-hour window)."""
        data = await self._post(f"{self.page_id}/messages", json={
            "recipient": {"id": recipient_id},
            "messaging_type": "RESPONSE",
            "message": {"text": text[:MESSENGER_TEXT_LIMIT]},
        })
        return data.get("message_id", "")

    async def reply_comment(self, comment_id: str, text: str) -> str:
        data = await self._post(f"{comment_id}/comments", data={"message": text[:8000]})
        return data.get("id", "")

    async def hide_comment(self, comment_id: str) -> None:
        await self._post(comment_id, data={"is_hidden": "true"})

    async def download(self, url: str, limit_bytes: int = 25 * 1024 * 1024) -> bytes:
        r = await self.http.get(url, follow_redirects=True)
        r.raise_for_status()
        if len(r.content) > limit_bytes:
            raise ValueError("attachment too large")
        return r.content

    async def post_facebook(self, caption: str, media: Path | None) -> str:
        if media and media.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            with media.open("rb") as fh:
                data = await self._post(f"{self.page_id}/photos",
                                        data={"caption": caption}, files={"source": (media.name, fh)})
            return data.get("post_id") or data.get("id", "")
        data = await self._post(f"{self.page_id}/feed", data={"message": caption})
        return data.get("id", "")

    async def post_instagram(self, caption: str, image_url: str) -> str:
        if not self.ig_user_id:
            raise GraphError("IG_USER_ID is not set")
        container = await self._post(f"{self.ig_user_id}/media", data={"image_url": image_url, "caption": caption})
        published = await self._post(f"{self.ig_user_id}/media_publish", data={"creation_id": container["id"]})
        return published.get("id", "")


class GraphError(Exception):
    def __init__(self, message: str, code: Any = None, subcode: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.subcode = subcode

    @property
    def outside_window(self) -> bool:
        # 10 / 2018278: message sent outside the allowed window.
        return self.code == 10 or self.subcode == 2018278
