#!/usr/bin/env python3
"""Measure bounded synthetic local chat latency without downloading/replacing models.

Run on the server while no user chat is generating. No paid provider, user prompt,
credentials, generated text or destructive cache-unload request is used.
"""
import argparse
import json
import statistics
import time
import urllib.request

BASE = "http://127.0.0.1:11434"
CASES = {
    "english": "Reply with exactly three words: local chat works",
    "bangla": "বাংলায় এক ছোট বাক্যে বলুন: আপনি কীভাবে সাহায্য করতে পারেন?",
}


def request(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.load(response)


def metrics(result, wall_seconds):
    if not result.get("done") or not result.get("message", {}).get("content", "").strip():
        raise ValueError("Local model returned an empty or incomplete response")
    output_seconds = result.get("eval_duration", 0) / 1e9
    return {
        "wall_seconds": round(wall_seconds, 3),
        "total_seconds": round(result.get("total_duration", 0) / 1e9, 3),
        "load_seconds": round(result.get("load_duration", 0) / 1e9, 3),
        "prompt_seconds": round(result.get("prompt_eval_duration", 0) / 1e9, 3),
        "prompt_tokens": result.get("prompt_eval_count", 0),
        "output_seconds": round(output_seconds, 3),
        "output_tokens": result.get("eval_count", 0),
        "output_tokens_per_second": round(result.get("eval_count", 0) / output_seconds, 2) if output_seconds else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", help="Installed model name; repeat for at most three candidates")
    parser.add_argument("--repeats", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--with-context-case", action="store_true", help="Also measure synthetic long-context overhead")
    args = parser.parse_args()
    models = args.model or ["qwen2.5:1.5b"]
    if len(models) > 3 or len(set(models)) != len(models):
        parser.error("Specify at most three distinct installed models")
    installed = {m["name"] for m in request("/api/tags").get("models", [])}
    if any(model not in installed for model in models):
        parser.error("All candidates must already be installed; this script never downloads models")
    cases = dict(CASES)
    if args.with_context_case:
        cases["synthetic_context"] = ("Reference note: this is a synthetic latency check. " * 150
                                       + "\nReply with exactly three words: local chat works")
    print(json.dumps({"version": request("/api/version").get("version"), "models": models,
                      "num_predict": 24, "num_ctx": 4096, "keep_alive": "30m",
                      "note": "First trial may include loading; later trials can reuse prompt cache."}), flush=True)
    for model in models:
        for case, prompt in cases.items():
            samples = []
            # First trial is reported separately rather than mislabeled as cold.
            for trial in range(args.repeats + 1):
                started = time.monotonic()
                result = request("/api/chat", {"model": model,
                    "messages": [{"role": "user", "content": prompt}], "stream": False,
                    "keep_alive": "30m", "options": {"num_ctx": 4096, "num_predict": 24, "temperature": 0}})
                measurement = metrics(result, time.monotonic() - started)
                print(json.dumps({"model": model, "case": case, "trial": trial,
                                  "phase": "initial" if trial == 0 else "warm", **measurement}), flush=True)
                if trial:
                    samples.append(measurement["wall_seconds"])
            print(json.dumps({"model": model, "case": case,
                              "warm_median_seconds": statistics.median(samples)}), flush=True)


if __name__ == "__main__":
    main()
