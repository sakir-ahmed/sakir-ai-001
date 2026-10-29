"""
OpenRouter client with spend tracking and a hard monthly budget.

Every call records its cost in the `spend` table. OpenRouter reports the
exact cost when `usage.include` is requested; if it does not, the price per
million tokens from dt-assistant.yaml is used. When the month's spend reaches
budget.monthly_usd, BudgetExceeded is raised and the pipeline falls back to a
holding reply plus an approval card, so customers are never left unanswered.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any

import httpx

from .config import Settings
from .db import Database

log = logging.getLogger("dt.llm")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class BudgetExceeded(Exception):
    pass


class LLMError(Exception):
    pass


class LLM:
    def __init__(self, api_key: str, settings: Settings, db: Database, notify=None) -> None:
        self.key = api_key
        self.settings = settings
        self.db = db
        self.notify = notify            # async callable(text) -> None, used for budget alerts
        self.http = httpx.AsyncClient(timeout=60, headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://datatechbd.com",
            "X-Title": "Sakir AI dt-assistant",
        })

    async def close(self) -> None:
        await self.http.aclose()

    @property
    def configured(self) -> bool:
        return bool(self.key)

    async def over_budget(self) -> bool:
        limit = float(self.settings.get("budget", "monthly_usd", default=26))
        return await self.db.month_spend() >= limit

    async def _check_budget(self) -> None:
        limit = float(self.settings.get("budget", "monthly_usd", default=26))
        alert_pct = float(self.settings.get("budget", "alert_at_percent", default=70))
        spent = await self.db.month_spend()
        if spent >= limit:
            raise BudgetExceeded(f"monthly budget ${limit:.2f} reached (${spent:.2f})")
        if spent >= limit * alert_pct / 100 and self.notify:
            month_key = "budget_alert_" + date.today().strftime("%Y-%m")
            if not await self.db.get_setting(month_key):
                await self.db.set_setting(month_key, True)
                await self.notify(f"Sales AI spend is ${spent:.2f} of ${limit:.2f} this month "
                                  f"({spent / limit:.0%}). At 100% it switches to holding replies.")

    async def chat(self, purpose: str, messages: list[dict[str, str]], *, json_mode: bool = False,
                   max_tokens: int = 500, temperature: float = 0.3) -> str:
        """Call the model configured for `purpose` (classify, reply, reply_premium)."""
        if not self.configured:
            raise LLMError("OPENROUTER_API_KEY is not set")
        await self._check_budget()
        model = self.settings.model(purpose if purpose != "followup" else "reply")
        body: dict[str, Any] = {
            "model": model.get("id", "deepseek/deepseek-v3.2"),
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "usage": {"include": True},
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        try:
            r = await self.http.post(OPENROUTER_URL, json=body)
        except httpx.HTTPError as exc:
            raise LLMError(f"network error: {exc}") from exc
        if r.status_code >= 400:
            raise LLMError(f"OpenRouter {r.status_code}: {r.text[:300]}")
        data = r.json()
        if "error" in data:
            raise LLMError(str(data["error"])[:300])

        usage = data.get("usage") or {}
        t_in, t_out = int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))
        cost = usage.get("cost")
        if cost is None:
            cost = (t_in * float(model.get("price_in", 0)) + t_out * float(model.get("price_out", 0))) / 1e6
        await self.db.add_spend(purpose, float(cost), t_in, t_out)

        try:
            return (data["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError) as exc:
            raise LLMError("empty model response") from exc


def parse_json(text: str) -> dict[str, Any]:
    """Models sometimes wrap JSON in ``` fences or add a sentence; extract the object."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])
