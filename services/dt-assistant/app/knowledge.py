"""
Knowledge for the sales pipeline:
  * sales/prompt.md          reply instructions (placeholders filled at run time)
  * sales/classify.md        classifier instructions
  * sales/templates.yaml     saved FAQ answers in bn / banglish / en
  * Qdrant collection        product facts, prices, playbook (built by indexer)

Files are re-read when they change on disk, so editing the knowledge repo
takes effect without a restart (the Qdrant index refreshes nightly or with
`sakir-ai reindex`).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx
import yaml

from .config import KNOWLEDGE_DIR

log = logging.getLogger("dt.knowledge")


class _CachedFile:
    def __init__(self, path: Path, parser=lambda s: s) -> None:
        self.path = path
        self.parser = parser
        self._mtime = -1.0
        self._value: Any = None

    def get(self, default: Any = None) -> Any:
        try:
            mtime = self.path.stat().st_mtime
        except FileNotFoundError:
            return default
        if mtime != self._mtime:
            self._value = self.parser(self.path.read_text(encoding="utf-8"))
            self._mtime = mtime
        return self._value


class Knowledge:
    def __init__(self, stt_url: str, qdrant_url: str, collection: str, base: Path = KNOWLEDGE_DIR) -> None:
        self.stt_url = stt_url.rstrip("/")
        self.qdrant_url = qdrant_url.rstrip("/")
        self.collection = collection
        self._prompt = _CachedFile(base / "sales" / "prompt.md")
        self._classify = _CachedFile(base / "sales" / "classify.md")
        self._templates = _CachedFile(base / "sales" / "templates.yaml", lambda s: yaml.safe_load(s) or {})
        self._pricing = base / "products" / "dt-restora" / "pricing.md"
        self.http = httpx.AsyncClient(timeout=30)

    async def close(self) -> None:
        await self.http.aclose()

    # ---- files ---------------------------------------------------------------
    def reply_prompt(self) -> str:
        return self._prompt.get(default="") or ""

    def classify_prompt(self) -> str:
        return self._classify.get(default="") or ""

    def templates(self) -> dict[str, dict[str, Any]]:
        """Saved FAQ answers; any template still containing TODO is ignored."""
        data = self._templates.get(default={}) or {}
        return {k: v for k, v in data.items()
                if isinstance(v, dict) and not any("TODO" in str(text) for text in v.values())}

    def pricing_ready(self) -> bool:
        """False while pricing.md still has TODO placeholders."""
        try:
            return "TODO" not in self._pricing.read_text(encoding="utf-8")
        except FileNotFoundError:
            return False

    # ---- search ----------------------------------------------------------------
    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Top matching knowledge chunks; empty list if search is unavailable."""
        try:
            r = await self.http.post(f"{self.stt_url}/embed", json={"text": query, "kind": "query"})
            r.raise_for_status()
            vector = r.json()["vector"]
            r = await self.http.post(
                f"{self.qdrant_url}/collections/{self.collection}/points/search",
                json={"vector": vector, "limit": limit, "with_payload": True, "score_threshold": 0.70},
            )
            r.raise_for_status()
            return [hit["payload"] for hit in r.json().get("result", [])]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            log.warning("knowledge search unavailable: %s", exc)
            return []

    async def transcribe(self, audio: bytes, filename: str = "voice.mp4") -> str:
        r = await self.http.post(f"{self.stt_url}/transcribe", files={"file": (filename, audio)},
                                 data={"language": "auto"}, timeout=300)
        r.raise_for_status()
        return r.json().get("text", "")
