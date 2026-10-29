"""Webhook signature and payload parsing."""
import hashlib
import hmac

from app.meta import parse_webhook, verify_signature


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_signature():
    body = b'{"object":"page"}'
    assert verify_signature("s3cret", body, sign("s3cret", body))
    assert not verify_signature("s3cret", body, sign("other", body))
    assert not verify_signature("s3cret", body, None)
    assert not verify_signature("", body, sign("", body))


def test_messenger_text_and_echo_and_audio():
    payload = {"object": "page", "entry": [{"messaging": [
        {"sender": {"id": "U1"}, "message": {"mid": "m1", "text": " dam koto? "}},
        {"sender": {"id": "PAGE1"}, "message": {"mid": "m2", "text": "our reply", "is_echo": True}},
        {"sender": {"id": "U2"}, "message": {"mid": "m3", "attachments": [
            {"type": "audio", "payload": {"url": "https://cdn/voice.mp4"}}]}},
        {"sender": {"id": "U3"}, "message": {"mid": "m4", "attachments": [{"type": "image"}]}},
        {"sender": {"id": "U4"}, "read": {"watermark": 1}},
    ]}]}
    events = parse_webhook(payload, "PAGE1")
    assert [e.meta_id for e in events] == ["m1", "m3"]
    assert events[0].text == "dam koto?" and events[0].channel == "messenger"
    assert events[1].audio_url == "https://cdn/voice.mp4"


def test_comments_skip_own_and_edits():
    payload = {"object": "page", "entry": [{"changes": [
        {"field": "feed", "value": {"item": "comment", "verb": "add", "comment_id": "c1", "post_id": "p1",
                                    "message": "price?", "from": {"id": "U9", "name": "Karim"}}},
        {"field": "feed", "value": {"item": "comment", "verb": "add", "comment_id": "c2",
                                    "message": "thanks", "from": {"id": "PAGE1"}}},
        {"field": "feed", "value": {"item": "comment", "verb": "edited", "comment_id": "c3",
                                    "message": "x", "from": {"id": "U9"}}},
        {"field": "feed", "value": {"item": "reaction", "verb": "add"}},
    ]}]}
    events = parse_webhook(payload, "PAGE1")
    assert len(events) == 1
    ev = events[0]
    assert (ev.channel, ev.target_id, ev.user_name, ev.post_id) == ("comment", "c1", "Karim", "p1")


def test_instagram_and_unknown_objects():
    ig = {"object": "instagram", "entry": [{"messaging": [
        {"sender": {"id": "IG7"}, "message": {"mid": "im1", "text": "hello"}}]}]}
    assert parse_webhook(ig, "PAGE1")[0].channel == "instagram"
    assert parse_webhook({"object": "user", "entry": []}, "PAGE1") == []
