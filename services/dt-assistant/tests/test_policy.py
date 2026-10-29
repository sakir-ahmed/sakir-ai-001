"""Unit tests for the decision rules (no network, no database)."""
from datetime import datetime, timedelta, timezone

from app import policy

AUTONOMY = {"auto_intents": [], "min_confidence": 0.85,
            "never_auto": ["price", "discount", "complaint", "order", "legal", "other"],
            "auto_send_templates": False}


def test_detect_language():
    assert policy.detect_language("দাম কত?") == "bn"
    assert policy.detect_language("bhai dam koto?") == "banglish"
    assert policy.detect_language("apnar software er price ki?") == "banglish"
    assert policy.detect_language("How much is the restaurant software?") == "en"
    assert policy.detect_language("") == "en"


def test_normalise_cleans_model_output():
    raw = {"intent": "PRICE", "language": "xx", "confidence": "1.7", "faq_key": "nope",
           "name": " Rahim ", "business": "null", "phone": "017-1234-5678"}
    out = policy.normalise_classification(raw, "dam koto bhai", {"demo"})
    assert out["intent"] == "price"
    assert out["language"] == "banglish"          # invalid model value -> heuristic
    assert out["confidence"] == 1.0                # clamped
    assert out["faq_key"] is None                  # unknown key dropped
    assert out["name"] == "Rahim"
    assert out["business"] is None
    assert out["phone"] == "01712345678"


def test_bangla_script_overrides_model_language():
    out = policy.normalise_classification({"intent": "price", "language": "en", "confidence": 0.9},
                                          "দাম কত টাকা?", set())
    assert out["language"] == "bn"


def test_unknown_intent_becomes_other():
    assert policy.normalise_classification({"intent": "weather"}, "hi", set())["intent"] == "other"


def test_price_is_never_automatic_even_if_listed():
    d = policy.decide("price", 0.99, False, {**AUTONOMY, "auto_intents": ["price"]})
    assert d.action == "draft" and not d.auto_send


def test_trusted_intent_auto_sends_only_when_confident():
    autonomy = {**AUTONOMY, "auto_intents": ["demo"]}
    assert policy.decide("demo", 0.90, False, autonomy).auto_send
    assert not policy.decide("demo", 0.60, False, autonomy).auto_send


def test_escalation_and_spam_and_pause():
    assert policy.decide("complaint", 0.9, False, AUTONOMY).action == "escalate"
    assert policy.decide("discount", 0.9, False, AUTONOMY).action == "escalate"
    assert policy.decide("spam", 0.9, False, AUTONOMY).action == "hide"
    assert policy.decide("price", 0.9, False, AUTONOMY, paused=True).action == "holding"
    assert policy.decide("price", 0.9, False, AUTONOMY, over_budget=True).action == "holding"
    # Spam is still hidden while paused.
    assert policy.decide("spam", 0.9, False, AUTONOMY, paused=True).action == "hide"


def test_templates_are_drafts_unless_allowed():
    assert not policy.decide("faq", 0.9, True, AUTONOMY).auto_send
    assert policy.decide("faq", 0.9, True, {**AUTONOMY, "auto_send_templates": True}).auto_send


def test_messenger_window():
    now = datetime.now(timezone.utc)
    assert policy.inside_window(now - timedelta(hours=23), 24, now)
    assert not policy.inside_window(now - timedelta(hours=23, minutes=58), 24, now)   # 5-min margin
    assert not policy.inside_window(None, 24, now)


def test_stage_only_moves_forward():
    assert policy.next_stage("new", "price") == "interested"
    assert policy.next_stage("demo", "price") == "demo"
    assert policy.next_stage("interested", "order") == "proposal"
    assert policy.next_stage("lost", "demo") == "lost"


def test_render_template_falls_back_to_english():
    t = {"en": "Hi from {assistant_name}", "bn": "নমস্কার"}
    assert policy.render_template(t, "banglish", {"assistant_name": "DT"}) == "Hi from DT"
    assert policy.render_template(t, "bn", {}) == "নমস্কার"
