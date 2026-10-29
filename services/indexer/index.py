"""
indexer — loads the knowledge base (Markdown files) into Qdrant.

Run: `sakir-ai reindex` (also nightly at 02:30 by sakir-index.timer).

Collections
  <product>   one per folder in knowledge/products/ ("dt-restora" -> "restora"),
              each also containing datatech/ and sales/ (company facts, playbook,
              glossary) so the sales agent finds everything in one search
  me          me/ and career/  (Sakir's profile, goals, CV)
  ops         servers/

How it works
  1. Split each .md file into chunks at headings (#, ##, ###), max ~1,500 chars.
  2. Embed chunks with the stt service (multilingual-e5-small, "passage:").
  3. Write into a NEW collection, then point the alias (e.g. "restora") at it
     and delete the old one, so searches never see a half-built index.

Files skipped: prompt.md and anything in inbox/ (unreviewed notes).
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import time
from pathlib import Path

import requests

KB = Path(os.environ.get("KNOWLEDGE_DIR", "/knowledge"))
QDRANT = os.environ.get("QDRANT_URL", "http://qdrant:6333")
EMBED = os.environ.get("EMBED_URL", "http://stt:8000/embed")
STT_HEALTH = os.environ.get("STT_HEALTH_URL", "http://stt:8000/health")
VECTOR_SIZE = 384
MAX_CHARS = 1500
SKIP_NAMES = {"prompt.md", "README.md"}


def wait_for_stt(timeout_s: int = 1800) -> None:
    """The stt service downloads models on first start; wait until it is ready."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if requests.get(STT_HEALTH, timeout=5).ok:
                return
        except requests.RequestException:
            pass
        print("waiting for stt models to load ...", flush=True)
        time.sleep(20)
    sys.exit("stt service not ready; try again later")


def chunks_of(path: Path) -> list[tuple[str, str]]:
    """Return (heading, text) chunks of a Markdown file."""
    text = path.read_text(encoding="utf-8", errors="replace")
    parts = re.split(r"\n(?=#{1,3} )", "\n" + text)
    out: list[tuple[str, str]] = []
    for part in parts:
        part = part.strip()
        if len(part) < 40:
            continue
        heading = part.splitlines()[0].lstrip("# ").strip() if part.startswith("#") else path.stem
        # Long sections are split on blank lines to stay under MAX_CHARS.
        buf = ""
        for para in part.split("\n\n"):
            if len(buf) + len(para) > MAX_CHARS and buf:
                out.append((heading, buf.strip()))
                buf = ""
            buf += para + "\n\n"
        if buf.strip():
            out.append((heading, buf.strip()))
    return out


def files_in(*folders: str) -> list[Path]:
    found: list[Path] = []
    for folder in folders:
        base = KB / folder
        if base.is_dir():
            found += [p for p in sorted(base.rglob("*.md")) if p.name not in SKIP_NAMES]
    return found


def plan() -> dict[str, list[Path]]:
    """Which files go into which collection."""
    collections: dict[str, list[Path]] = {}
    products = KB / "products"
    if products.is_dir():
        for product_dir in sorted(p for p in products.iterdir() if p.is_dir()):
            name = product_dir.name.removeprefix("dt-")
            collections[name] = files_in(f"products/{product_dir.name}", "datatech", "sales")
    collections["me"] = files_in("me", "career")
    collections["ops"] = files_in("servers")
    return collections


def embed(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for i in range(0, len(texts), 32):
        r = requests.post(EMBED, json={"texts": texts[i:i + 32], "kind": "passage"}, timeout=300)
        r.raise_for_status()
        vectors += r.json()["vectors"]
    return vectors


def point_id(collection: str, file: str, text: str) -> int:
    return int(hashlib.sha256(f"{collection}|{file}|{text}".encode()).hexdigest()[:15], 16)


def build(alias: str, files: list[Path]) -> int:
    records: list[tuple[str, str, str]] = []
    for path in files:
        rel = str(path.relative_to(KB))
        records += [(rel, heading, text) for heading, text in chunks_of(path)]
    if not records:
        print(f"{alias}: no files, skipped")
        return 0

    new_name = f"{alias}_{int(time.time())}"
    requests.put(f"{QDRANT}/collections/{new_name}",
                 json={"vectors": {"size": VECTOR_SIZE, "distance": "Cosine"}}, timeout=30).raise_for_status()

    vectors = embed([f"{h}\n{t}" for _, h, t in records])
    points = [
        {"id": point_id(alias, f, t), "vector": v, "payload": {"file": f, "heading": h, "text": t}}
        for (f, h, t), v in zip(records, vectors)
    ]
    for i in range(0, len(points), 128):
        requests.put(f"{QDRANT}/collections/{new_name}/points?wait=true",
                     json={"points": points[i:i + 128]}, timeout=120).raise_for_status()

    # Atomically point the alias at the new collection.
    existing = requests.get(f"{QDRANT}/collections", timeout=30).json()["result"]["collections"]
    actions: list[dict] = []
    aliases = requests.get(f"{QDRANT}/aliases", timeout=30).json()["result"]["aliases"]
    if any(a["alias_name"] == alias for a in aliases):
        actions.append({"delete_alias": {"alias_name": alias}})
    # A plain collection with the alias' name (from an old version) must go first.
    if any(c["name"] == alias for c in existing):
        requests.delete(f"{QDRANT}/collections/{alias}", timeout=30)
    actions.append({"create_alias": {"collection_name": new_name, "alias_name": alias}})
    requests.post(f"{QDRANT}/collections/aliases", json={"actions": actions}, timeout=30).raise_for_status()

    # Remove older builds of this alias.
    for c in existing:
        if re.fullmatch(rf"{re.escape(alias)}_\d+", c["name"]) and c["name"] != new_name:
            requests.delete(f"{QDRANT}/collections/{c['name']}", timeout=30)

    print(f"{alias}: {len(points)} chunks from {len(files)} files")
    return len(points)


def main() -> None:
    wait_for_stt()
    total = 0
    for alias, files in plan().items():
        total += build(alias, files)
    pricing = KB / "products" / "dt-restora" / "pricing.md"
    if pricing.exists() and "TODO" in pricing.read_text(encoding="utf-8"):
        print("WARNING: products/dt-restora/pricing.md still contains TODO", flush=True)
    print(f"done: {total} chunks indexed")


if __name__ == "__main__":
    main()
