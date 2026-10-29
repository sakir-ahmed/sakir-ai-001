"""HTTP layer: Meta verification handshake and signature enforcement."""
import asyncio
import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)          # no `with`: lifespan (DB, bots) is not started
main.S.queue = asyncio.Queue()


def test_verify_handshake():
    ok = client.get("/meta/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "test-verify-token",
                                             "hub.challenge": "12345"})
    assert ok.status_code == 200 and ok.text == "12345"
    bad = client.get("/meta/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "wrong",
                                              "hub.challenge": "1"})
    assert bad.status_code == 403


def test_events_need_a_valid_signature():
    body = json.dumps({"object": "page", "entry": [{"messaging": [
        {"sender": {"id": "U1"}, "message": {"mid": "m1", "text": "hi"}}]}]}).encode()
    assert client.post("/meta/webhook", content=body).status_code == 401

    sig = "sha256=" + hmac.new(b"test-app-secret", body, hashlib.sha256).hexdigest()
    r = client.post("/meta/webhook", content=body, headers={"X-Hub-Signature-256": sig})
    assert r.status_code == 200 and r.text == "EVENT_RECEIVED"
    assert main.S.queue.qsize() == 1


def test_internal_api_requires_token():
    assert client.get("/internal/summary").status_code == 401
    assert client.post("/internal/pause", headers={"Authorization": "Bearer nope"}).status_code == 401
