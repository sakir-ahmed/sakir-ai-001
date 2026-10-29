"""
Settings: secrets come from environment variables (secrets/dt-assistant.env),
behaviour from /config/dt-assistant.yaml. Both are read once at start-up;
restart the container after changing them.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

CONFIG_PATH = Path(os.environ.get("DT_CONFIG", "/config/dt-assistant.yaml"))
KNOWLEDGE_DIR = Path(os.environ.get("KNOWLEDGE_DIR", "/knowledge"))
OUTBOX_DIR = Path(os.environ.get("OUTBOX_DIR", "/outbox"))
LOCAL_TZ = ZoneInfo(os.environ.get("TZ", "Asia/Dhaka"))


@dataclass(frozen=True)
class Secrets:
    database_url: str
    owner_id: str
    sales_bot_token: str
    openrouter_key: str
    internal_token: str
    meta_app_secret: str
    meta_verify_token: str
    meta_page_id: str
    meta_page_token: str
    ig_user_id: str
    public_base_url: str
    stt_url: str
    qdrant_url: str

    @property
    def meta_ready(self) -> bool:
        return bool(self.meta_app_secret and self.meta_page_token and self.meta_page_id)

    @property
    def telegram_ready(self) -> bool:
        return bool(self.sales_bot_token and self.owner_id)


def load_secrets() -> Secrets:
    env = os.environ.get
    return Secrets(
        database_url=env("DATABASE_URL", ""),
        owner_id=env("TELEGRAM_OWNER_ID", ""),
        sales_bot_token=env("SALES_BOT_TOKEN", ""),
        openrouter_key=env("OPENROUTER_API_KEY", ""),
        internal_token=env("INTERNAL_API_TOKEN", ""),
        meta_app_secret=env("META_APP_SECRET", ""),
        meta_verify_token=env("META_VERIFY_TOKEN", ""),
        meta_page_id=env("META_PAGE_ID", ""),
        meta_page_token=env("META_PAGE_TOKEN", ""),
        ig_user_id=env("IG_USER_ID", ""),
        public_base_url=env("PUBLIC_BASE_URL", "").rstrip("/"),
        stt_url=env("STT_URL", "http://stt:8000"),
        qdrant_url=env("QDRANT_URL", "http://qdrant:6333"),
    )


@dataclass
class Settings:
    """Typed view of dt-assistant.yaml with safe defaults."""
    raw: dict[str, Any] = field(default_factory=dict)

    def get(self, *keys: str, default: Any = None) -> Any:
        node: Any = self.raw
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    # Convenience accessors used across the app.
    @property
    def assistant_name(self) -> str:
        return self.get("assistant_name", default="Datatech BD Assistant")

    @property
    def company(self) -> str:
        return self.get("company", default="Datatech BD Ltd.")

    @property
    def product(self) -> str:
        return self.get("product", default="restora")

    @property
    def collection(self) -> str:
        return self.get("qdrant_collection", default="restora")

    @property
    def graph_version(self) -> str:
        return self.get("meta", "graph_version", default="v25.0")

    @property
    def window_hours(self) -> float:
        return float(self.get("meta", "messenger_window_hours", default=24))

    def model(self, purpose: str) -> dict[str, Any]:
        return self.get("models", purpose, default={}) or {}

    def holding_reply(self, language: str) -> str:
        replies = self.get("holding_reply", default={}) or {}
        return replies.get(language) or replies.get("en") or "Thank you! Our team will reply shortly."


def load_settings(path: Path = CONFIG_PATH) -> Settings:
    with open(path, encoding="utf-8") as fh:
        return Settings(raw=yaml.safe_load(fh) or {})
