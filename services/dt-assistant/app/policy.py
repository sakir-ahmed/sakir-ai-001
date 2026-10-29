"""
Pure decision logic — no network, no database — so it can be unit-tested.

The central function is `decide()`, which turns a classified message into one
of a few actions. The rules follow the master plan:

  * spam                         -> hide (comments) / ignore
  * complaint, discount, legal   -> automatic holding reply + escalation card
  * FAQ with a saved template    -> template (auto only if allowed)
  * everything else              -> AI draft; sent automatically ONLY when the
                                    intent is in autonomy.auto_intents, not in
                                    never_auto, and confidence >= min_confidence
  * paused or over budget        -> holding reply (+ card so Sakir can answer)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

INTENTS = ("faq", "price", "demo", "order", "support", "complaint", "discount", "legal", "spam", "greeting", "other")
LANGUAGES = ("bn", "banglish", "en")
ESCALATE = {"complaint", "discount", "legal"}

# Common Banglish words; enough to tell Banglish from English in short messages.
_BANGLISH_WORDS = {
    "ami", "apni", "apnar", "amar", "ki", "koto", "dam", "taka", "ache", "achhe", "nai", "na",
    "chai", "lagbe", "kivabe", "kemne", "keno", "kobe", "hobe", "korte", "kori", "korbo",
    "bhai", "vai", "apu", "dada", "jante", "janaben", "dorkar", "valo", "bhalo", "thik",
    "ase", "asen", "den", "diben", "dite", "kothay", "kono", "ekta", "acha", "accha",
    "dhonnobad", "shubho", "software", "restaurant",   # the last two are neutral: weight low
}
_BANGLA_SCRIPT = re.compile(r"[ঀ-৿]")


def detect_language(text: str) -> str:
    """bn = Bangla script, banglish = Bangla in Latin letters, en = English."""
    if not text:
        return "en"
    if len(_BANGLA_SCRIPT.findall(text)) >= 2:
        return "bn"
    words = re.findall(r"[a-zA-Z]+", text.lower())
    if not words:
        return "en"
    hits = sum(1 for w in words if w in _BANGLISH_WORDS and w not in {"software", "restaurant"})
    return "banglish" if hits >= 1 and hits / len(words) >= 0.15 else "en"


def normalise_classification(raw: dict[str, Any], text: str, faq_keys: set[str]) -> dict[str, Any]:
    """Clean the model's JSON so the rest of the code can trust it."""
    intent = str(raw.get("intent", "other")).lower().strip()
    if intent not in INTENTS:
        intent = "other"
    language = str(raw.get("language", "")).lower().strip()
    if language not in LANGUAGES:
        language = detect_language(text)
    # Script is a hard signal; trust it over the model.
    if _BANGLA_SCRIPT.search(text) and len(_BANGLA_SCRIPT.findall(text)) >= 2:
        language = "bn"
    try:
        confidence = max(0.0, min(1.0, float(raw.get("confidence", 0))))
    except (TypeError, ValueError):
        confidence = 0.0
    faq_key = raw.get("faq_key")
    faq_key = faq_key if isinstance(faq_key, str) and faq_key in faq_keys else None
    phone = _clean_phone(raw.get("phone"))
    return {
        "intent": intent,
        "language": language,
        "confidence": confidence,
        "faq_key": faq_key,
        "name": _clean_str(raw.get("name"), 80),
        "business": _clean_str(raw.get("business"), 120),
        "phone": phone,
    }


def _clean_str(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:limit] if value and value.lower() not in {"null", "none", "unknown", "n/a"} else None


def _clean_phone(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    digits = re.sub(r"[^\d+]", "", value)
    return digits if 10 <= len(digits.lstrip("+")) <= 14 else None


@dataclass(frozen=True)
class Decision:
    action: str          # ignore | hide | holding | escalate | template | draft
    auto_send: bool      # send without Sakir's approval
    reason: str


def decide(intent: str, confidence: float, has_template: bool, autonomy: dict[str, Any],
           paused: bool = False, over_budget: bool = False) -> Decision:
    """What to do with a classified customer message."""
    auto_intents = set(autonomy.get("auto_intents") or [])
    never_auto = set(autonomy.get("never_auto") or [])
    min_conf = float(autonomy.get("min_confidence", 0.85))

    if intent == "spam":
        return Decision("hide", True, "spam")
    if paused:
        return Decision("holding", True, "automatic replies are paused")
    if over_budget:
        return Decision("holding", True, "monthly model budget reached")
    if intent in ESCALATE:
        return Decision("escalate", False, f"{intent} always goes to Sakir")
    if intent == "faq" and has_template:
        auto = bool(autonomy.get("auto_send_templates")) and "faq" not in never_auto
        return Decision("template", auto, "saved template")

    auto = intent in auto_intents and intent not in never_auto and confidence >= min_conf
    reason = "auto: trusted intent" if auto else (
        f"draft: '{intent}' is not on the automatic list" if intent not in auto_intents or intent in never_auto
        else f"draft: confidence {confidence:.2f} < {min_conf:.2f}")
    return Decision("draft", auto, reason)


def inside_window(last_inbound_at: datetime | None, window_hours: float, now: datetime | None = None,
                  margin_minutes: int = 5) -> bool:
    """True if a Messenger reply is still allowed (customer wrote within the window)."""
    if last_inbound_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    return now - last_inbound_at < timedelta(hours=window_hours) - timedelta(minutes=margin_minutes)


def next_stage(current: str, intent: str) -> str:
    """Move a lead forward only (never backward) based on what they asked."""
    order = ["new", "interested", "demo", "proposal", "won"]
    if current not in order:            # 'lost' or custom stages are left alone
        return current
    target = {"price": "interested", "faq": "interested", "demo": "demo", "order": "proposal"}.get(intent)
    if target and order.index(target) > order.index(current):
        return target
    return current


def render_template(template: dict[str, str], language: str, values: dict[str, str]) -> str:
    """Pick the template text for a language (fallback: en) and fill {placeholders}."""
    text = template.get(language) or template.get("en") or next(iter(template.values()), "")
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text.strip()


def truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
