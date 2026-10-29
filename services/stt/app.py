"""
stt — speech-to-text and text embeddings for Sakir AI (CPU only).

Models (downloaded to /models on first start):
  * faster-whisper multilingual (STT_WHISPER_MODEL, default "small")
      - detects the spoken language
      - transcribes English and other non-Bangla speech
  * BanglaSpeech2Text (STT_BN_MODEL, default "small", ~1 GB; "large" ~3 GB)
      - Whisper fine-tuned for Bangla, used when Bangla is detected
  * intfloat/multilingual-e5-small (384-dim) for knowledge-base search

Endpoints
  GET  /health                        200 once all models are loaded
  POST /transcribe                    multipart file=<audio>, language=auto|bn|en
                                      -> {"language", "text", "seconds"}
  POST /v1/audio/transcriptions       Whisper-API compatible (file=, model=)
                                      -> {"text"}
  POST /embed                         {"text": "...", "kind": "query"|"passage"}
                                      or {"texts": [...], "kind": ...}
                                      -> {"vector": [...]} or {"vectors": [[...]]}

Audio is converted with ffmpeg to 16 kHz mono WAV; Telegram/Messenger voice
notes (OGG/Opus, M4A, MP4) all work.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import threading
import time

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

os.environ.setdefault("HF_HOME", "/models")

logging.basicConfig(level=logging.INFO, format="%(asctime)s stt %(levelname)s %(message)s")
log = logging.getLogger("stt")

WHISPER_MODEL = os.environ.get("STT_WHISPER_MODEL", "small")
BN_MODEL = os.environ.get("STT_BN_MODEL", "small")
EMBED_MODEL = os.environ.get("STT_EMBED_MODEL", "intfloat/multilingual-e5-small")
THREADS = int(os.environ.get("STT_THREADS", "4"))
MAX_AUDIO_BYTES = 25 * 1024 * 1024   # 25 MB, about 20+ minutes of voice

app = FastAPI(title="stt", docs_url=None, redoc_url=None, openapi_url=None)

# Models load in the background so the container starts quickly; /health
# reports ready only when all three are loaded.
_models: dict[str, object] = {}
_ready = threading.Event()
_load_error: list[str] = []
# CPU inference is not parallel-friendly; one transcription at a time.
_stt_lock = threading.Lock()


def _load_models() -> None:
    try:
        from faster_whisper import WhisperModel
        from banglaspeech2text import Speech2Text
        from sentence_transformers import SentenceTransformer

        log.info("loading whisper model %s", WHISPER_MODEL)
        _models["whisper"] = WhisperModel(
            WHISPER_MODEL, device="cpu", compute_type="int8",
            cpu_threads=THREADS, download_root="/models/whisper",
        )
        log.info("loading Bangla model %s (first start converts it, takes minutes)", BN_MODEL)
        _models["bangla"] = Speech2Text(BN_MODEL, device="cpu", compute_type="int8", cpu_threads=THREADS)
        log.info("loading embedding model %s", EMBED_MODEL)
        _models["embed"] = SentenceTransformer(EMBED_MODEL, device="cpu", cache_folder="/models/embed")
        _ready.set()
        log.info("all models ready")
    except Exception as exc:  # surfaced through /health
        log.exception("model loading failed")
        _load_error.append(str(exc))


threading.Thread(target=_load_models, daemon=True).start()


def _require_ready() -> None:
    if _load_error:
        raise HTTPException(status_code=500, detail=f"model load failed: {_load_error[0]}")
    if not _ready.is_set():
        raise HTTPException(status_code=503, detail="models are still loading")


def _to_wav(upload: UploadFile) -> str:
    """Save the upload and convert it to 16 kHz mono WAV. Returns the WAV path."""
    data = upload.file.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="audio file too large (max 25 MB)")
    if not data:
        raise HTTPException(status_code=400, detail="empty audio file")
    src = tempfile.NamedTemporaryFile(delete=False, suffix=".audio", dir="/tmp")
    src.write(data)
    src.close()
    wav = src.name + ".wav"
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
         "-i", src.name, "-ar", "16000", "-ac", "1", wav],
        capture_output=True, text=True, timeout=120,
    )
    os.unlink(src.name)
    if proc.returncode != 0:
        raise HTTPException(status_code=400, detail=f"could not decode audio: {proc.stderr[:200]}")
    return wav


def _transcribe(wav: str, language: str = "auto") -> dict[str, object]:
    whisper = _models["whisper"]
    bangla = _models["bangla"]
    started = time.time()
    try:
        with _stt_lock:
            # faster-whisper detects the language before decoding; segments are
            # lazy, so for Bangla we never decode with the general model.
            lang_hint = None if language == "auto" else language
            segments, info = whisper.transcribe(wav, beam_size=1, language=lang_hint, vad_filter=True)
            detected = info.language
            if detected == "bn":
                text = bangla.recognize(wav)
            else:
                text = " ".join(s.text.strip() for s in segments)
    finally:
        if os.path.exists(wav):
            os.unlink(wav)
    return {"language": detected, "text": str(text).strip(), "seconds": round(time.time() - started, 1)}


@app.get("/health")
def health() -> dict[str, str]:
    _require_ready()
    return {"status": "ok"}


@app.post("/transcribe")
def transcribe(file: UploadFile = File(...), language: str = Form("auto")) -> dict[str, object]:
    _require_ready()
    if language not in ("auto", "bn", "en"):
        raise HTTPException(status_code=400, detail="language must be auto, bn or en")
    return _transcribe(_to_wav(file), language)


@app.post("/v1/audio/transcriptions")
def openai_compatible(file: UploadFile = File(...), model: str = Form("whisper-1")) -> dict[str, object]:
    """Drop-in for clients that speak the Whisper API (model name is ignored)."""
    _require_ready()
    return {"text": _transcribe(_to_wav(file))["text"]}


class EmbedRequest(BaseModel):
    text: str | None = Field(default=None, max_length=8000)
    texts: list[str] | None = Field(default=None, max_length=256)
    kind: str = Field(default="query", pattern="^(query|passage)$")


@app.post("/embed")
def embed(req: EmbedRequest) -> dict[str, object]:
    """e5 models expect 'query: ' for questions and 'passage: ' for documents."""
    _require_ready()
    model = _models["embed"]
    prefix = f"{req.kind}: "
    if req.texts is not None:
        vectors = model.encode([prefix + t for t in req.texts], normalize_embeddings=True, batch_size=16)
        return {"vectors": [v.tolist() for v in vectors]}
    if req.text is None:
        raise HTTPException(status_code=400, detail="send 'text' or 'texts'")
    return {"vector": model.encode(prefix + req.text, normalize_embeddings=True).tolist()}
