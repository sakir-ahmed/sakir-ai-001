"""
tts — text-to-speech for spoken replies (Bangla and English).

Uses edge-tts (Microsoft Edge online neural voices). It needs internet access
and is not an official Microsoft API, so voices can change; if it breaks,
switch Hermes to a paid TTS (e.g. ElevenLabs) for spoken replies.

Endpoints
  GET  /health
  GET  /voices?lang=bn          list available voices for a language prefix
  POST /speak                   {"text": "...", "lang": "bn"|"en", "voice": optional}
                                -> audio/mpeg (MP3)
"""
from __future__ import annotations

import os
import tempfile

import edge_tts
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Defaults can be overridden with environment variables.
VOICES = {
    "bn": os.environ.get("TTS_VOICE_BN", "bn-BD-NabanitaNeural"),
    "en": os.environ.get("TTS_VOICE_EN", "en-US-AndrewNeural"),
}

app = FastAPI(title="tts", docs_url=None, redoc_url=None, openapi_url=None)


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=3000)
    lang: str = Field(default="bn", pattern="^(bn|en)$")
    voice: str | None = Field(default=None, max_length=64)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/voices")
async def voices(lang: str = "bn") -> list[str]:
    all_voices = await edge_tts.list_voices()
    return sorted(v["ShortName"] for v in all_voices if v["Locale"].lower().startswith(lang.lower()))


@app.post("/speak")
async def speak(req: SpeakRequest, background: BackgroundTasks) -> FileResponse:
    voice = req.voice or VOICES[req.lang]
    fd, path = tempfile.mkstemp(suffix=".mp3", dir="/tmp")
    os.close(fd)
    try:
        await edge_tts.Communicate(req.text, voice).save(path)
    except Exception as exc:
        os.unlink(path)
        raise HTTPException(status_code=502, detail=f"tts failed: {exc}") from exc
    background.add_task(os.unlink, path)   # delete after the response is sent
    return FileResponse(path, media_type="audio/mpeg", filename="reply.mp3")
