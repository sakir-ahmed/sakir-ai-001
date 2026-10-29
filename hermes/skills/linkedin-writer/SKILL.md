---
name: linkedin-writer
description: Draft LinkedIn posts in Sakir's voice from his real work and learning, to build his personal brand toward CTO. Use for "/linkedin", "LinkedIn post", "personal branding", and the Tuesday/Friday 11:00 runs.
---
# LinkedIn writer

## Inputs
- `sakir-persona` and `/knowledge/me/voice.md` (copy his style from the examples)
- `/knowledge/datatech/case-studies.md` for real product results (public clients only)
- `/knowledge/me/goals.md` (brand: software architecture, microservices, leading teams, building products)
- Recent material: ask Sakir "What did you ship, learn or decide this week?" if nothing is in
  `/knowledge/inbox/` from the last 7 days.

## Write two drafts
Formats that work (pick two different ones):
1. Lesson learned — situation, what went wrong/right, the lesson, a question to readers.
2. How I built it — a Datatech BD product decision (architecture, stack, trade-off).
3. Short opinion — one clear take on architecture, AI tools or engineering leadership.
4. Milestone — product launch or certification, with gratitude and what is next.

Rules
- 120–220 words, short paragraphs, first line is the hook (under 12 words).
- Concrete details over adjectives; no invented numbers.
- Max 3 hashtags at the end. No Grameenphone/eGeneration internals.
- English by default.

Save to `/outbox/linkedin/<YYYY-MM-DD>-draft-1.md` and `-draft-2.md`, send both to Sakir.
If he approves one and gives a time, schedule it:
`python3 /opt/sakir-tools/sakir.py content schedule --product brand --platform linkedin --at "<time>" --caption-file <file>`
(LinkedIn posts arrive as a ready-to-paste reminder.)
