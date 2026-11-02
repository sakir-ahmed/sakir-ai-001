#!/usr/bin/env python3
"""Verify the private UI and local inference with a synthetic bounded prompt."""
import json
import time
import urllib.request


def request(url, payload=None, timeout=15):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def main():
    models = request("http://127.0.0.1:11434/api/tags")
    names = [item["name"] for item in models.get("models", [])]
    model = "qwen2.5:1.5b"
    assert model in names, f"Expected local model is missing: {model}"
    print(json.dumps({"ollama_api": "ok", "models": names}), flush=True)
    started = time.monotonic()
    result = request("http://127.0.0.1:11434/api/generate", {
        "model": model, "prompt": "Reply with exactly: local AI works",
        "stream": False, "options": {"num_predict": 24, "temperature": 0},
        "keep_alive": "2m",
    }, timeout=120)
    assert result.get("done") and str(result.get("response", "")).strip(), "Empty or incomplete inference"
    print(json.dumps({"local_inference": "ok", "seconds": round(time.monotonic() - started, 2),
                      "paid_api_used": False}), flush=True)
    health = request("http://127.0.0.1:8082/health")
    assert health.get("status") is True, "UI health did not pass"
    with urllib.request.urlopen("http://127.0.0.1:8082/", timeout=15) as response:
        page = response.read(2_000_000).decode()
        assert response.status == 200 and "<html" in page.lower(), "UI page is missing"
    print(json.dumps({"webui_health": "ok", "webui_page": "ok",
                      "authenticated_chat_and_voice": "not_tested"}))


if __name__ == "__main__":
    main()
