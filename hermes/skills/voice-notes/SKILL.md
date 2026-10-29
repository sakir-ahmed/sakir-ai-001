---
name: voice-notes
description: Understand Sakir's Telegram voice notes in Bangla, Banglish or English, and reply with audio when he asks. Use whenever a message is a voice note or audio file, or when Sakir asks for a spoken reply.
---
# Voice notes

## Incoming voice note
If Hermes has not already transcribed it, run on the saved audio file:
```bash
python3 /opt/sakir-tools/sakir.py voice transcribe <path-to-audio-file>
```
It returns `{"language": "bn"|"en"|..., "text": "..."}`. Then treat the text exactly
like a typed message from Sakir and do what it asks. Start your reply with one
line showing what you understood, e.g. `(heard: "aj er sales summary dao")`, so
Sakir can correct a mistake.

If transcription fails or the text looks wrong, ask Sakir to repeat or type it.

## Spoken reply (only when Sakir asks: "voice e bolo", "reply in voice", "audio dao")
```bash
python3 /opt/sakir-tools/sakir.py voice speak "<short reply text>" --lang bn
```
Send the returned MP3 file. Keep spoken replies under 60 seconds (~120 words).
