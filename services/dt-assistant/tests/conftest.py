"""
Test setup. Environment variables must be set BEFORE app modules are imported.

Unit tests need nothing else. Pipeline tests need a throwaway Postgres:
    TEST_DATABASE_URL=postgresql://user@127.0.0.1:5432/sakirai_test pytest
They are skipped when TEST_DATABASE_URL is not set. All external APIs
(OpenRouter, Meta, Telegram, stt, Qdrant) are mocked with respx.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]           # bundle root (sakir-ai/)
os.environ.setdefault("DT_CONFIG", str(ROOT / "config" / "dt-assistant.yaml"))
os.environ.setdefault("KNOWLEDGE_DIR", str(ROOT / "knowledge-templates"))
os.environ.setdefault("TZ", "Asia/Dhaka")
os.environ.setdefault("DATABASE_URL", os.environ.get("TEST_DATABASE_URL", "postgresql://invalid/none"))
os.environ.setdefault("META_APP_SECRET", "test-app-secret")
os.environ.setdefault("META_VERIFY_TOKEN", "test-verify-token")
os.environ.setdefault("META_PAGE_ID", "PAGE1")
os.environ.setdefault("META_PAGE_TOKEN", "page-token")
os.environ.setdefault("SALES_BOT_TOKEN", "123:abc")
os.environ.setdefault("TELEGRAM_OWNER_ID", "999")
os.environ.setdefault("OPENROUTER_API_KEY", "or-test")
os.environ.setdefault("INTERNAL_API_TOKEN", "internal-test")
os.environ.setdefault("STT_URL", "http://stt:8000")
os.environ.setdefault("QDRANT_URL", "http://qdrant:6333")
