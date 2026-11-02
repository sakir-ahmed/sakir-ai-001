"""
OpenRouter client with spend tracking and a hard monthly budget.

Each successful response records actual provider usage or a conservative price-ceiling
estimate. Free-first routing uses compatible zero-price inference, a bounded cheap
fallback and an explicit stronger-model purpose. Paid requests stop at the monthly
budget; free inference remains eligible. Provider key caps are the hard boundary
across services, ambiguous network outcomes and any unreported usage.
"""
from __future__ import annotations

import asyncio
import json
import math
import time
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
        self._call_lock = asyncio.Lock()
        self._free_until = 0.0
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
        if self.settings.get("routing", "free_first", default=False):
            return False  # paid cap must not disable still-available free inference
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
        # Serialize check/call/accounting within this worker. Provider key limits
        # remain the hard boundary across processes and unknown network outcomes.
        async with self._call_lock:
            return await self._chat(purpose, messages, json_mode, max_tokens, temperature)

    async def _chat(self, purpose, messages, json_mode, max_tokens, temperature):
        route = self.settings.get("routing", default={}) or {}
        enabled = bool(route.get("free_first", False))
        if not enabled:
            await self._check_budget()
        model = self.settings.model("reply" if purpose == "followup" else purpose)
        complex_task = purpose in route.get("paid_purposes", [])
        free = [{"id": name, "price_in": 0, "price_out": 0}
                for name in route.get("free_models", ["openrouter/free"])]
        if any(not (m["id"] == "openrouter/free" or m["id"].endswith(":free")) for m in free):
            raise LLMError("free_models must contain only free model IDs")
        if not enabled:
            candidates = [model]
        elif complex_task and route.get("allow_paid", True):
            candidates = [model] + free
        else:
            candidates = free
            if route.get("allow_paid", True):
                candidates += [self.settings.model("paid_fallback")]
        if len(json.dumps(messages, ensure_ascii=False).encode()) > int(route.get("max_input_bytes", 24000)):
            raise LLMError("request exceeds configured input size limit")
        max_tokens = min(max_tokens, int(route.get("max_output_tokens", 500)))
        if max_tokens <= 0:
            raise LLMError("max_output_tokens must be positive")
        attempts = 0
        last_error = "no eligible model (free cooldown or paid disabled)"
        for candidate in candidates:
            name = candidate.get("id")
            if not name:
                continue
            is_free = name == "openrouter/free" or name.endswith(":free")
            if enabled and is_free and time.monotonic() < self._free_until:
                continue
            if attempts >= min(4, max(1, int(route.get("max_attempts", 2)))):
                break
            price_in = float(candidate.get("price_in", 0))
            price_out = float(candidate.get("price_out", 0))
            if not all(math.isfinite(p) and p >= 0 for p in [price_in, price_out]):
                raise LLMError("invalid model price ceiling")
            if not is_free and (price_in <= 0 or price_out <= 0):
                raise LLMError("paid model requires explicit price ceilings")
            if not is_free:
                try:
                    await self._check_budget()
                except BudgetExceeded:
                    last_error = "paid budget exhausted"
                    continue
                # Conservative UTF-8 byte allowance, plus chat framing, bounded
                # output and explicit provider per-million-token price ceilings.
                input_bound = len(json.dumps(messages, ensure_ascii=False).encode()) + 512 * len(messages)
                reserve = (input_bound * price_in + max_tokens * price_out) / 1e6
                remaining = float(self.settings.get("budget", "monthly_usd", default=26)) - await self.db.month_spend()
                if reserve > remaining:
                    last_error = "paid request would exceed remaining budget"
                    continue
            body = {
                "model": name, "messages": messages, "max_tokens": max_tokens,
                "temperature": temperature, "usage": {"include": True},
                "provider": {"sort": "price", "require_parameters": True,
                             "data_collection": route.get("data_collection", "deny"),
                             "max_price": {"prompt": price_in, "completion": price_out, "request": 0}},
            }
            if json_mode:
                body["response_format"] = {"type": "json_object"}
            attempts += 1
            try:
                response = await self.http.post(OPENROUTER_URL, json=body)
            except httpx.HTTPError:
                last_error = "model network failure"
                continue
            # Never include upstream bodies (which may echo prompts) in logs.
            if response.status_code >= 400:
                code = response.status_code
                last_error = f"OpenRouter HTTP {code}"
                if is_free and code == 429:
                    try:
                        delay = float(response.headers.get("Retry-After", 60))
                    except ValueError:
                        delay = 60
                    self._free_until = time.monotonic() + min(86400, max(60, delay))
                if code not in {404, 408, 429, 500, 502, 503, 504, 524, 529}:
                    raise LLMError(last_error)
                continue
            try:
                data = response.json()
            except ValueError:
                raise LLMError("invalid upstream response") from None
            if "error" in data:
                # No blind retry of embedded errors: quota/auth/moderation must
                # not silently trigger an unaccounted paid request.
                raise LLMError("OpenRouter returned an error payload")
            usage = data.get("usage") or {}
            t_in, t_out = int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))
            cost = usage.get("cost")
            if cost is None:
                cost = (t_in * price_in + t_out * price_out) / 1e6
                if not is_free and not usage:
                    cost = reserve  # conservative estimate when usage is absent
            if not math.isfinite(float(cost)) or float(cost) < 0:
                raise LLMError("invalid upstream usage cost")
            cost = float(cost)
            await self.db.add_spend(purpose, cost, t_in, t_out)
            log.info("model purpose=%s selected=%s free=%s usd=%.6f", purpose, data.get("model", name), is_free, cost)
            try:
                content = data["choices"][0]["message"]["content"]
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("empty content")
                if json_mode:
                    parsed = parse_json(content)
                    if not isinstance(parsed, dict):
                        raise ValueError("expected JSON object")
                return content.strip()
            except (KeyError, IndexError, TypeError, ValueError):
                last_error = "empty or invalid model output"
                # The malformed response is already cost-accounted above.
        raise LLMError(last_error)


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
