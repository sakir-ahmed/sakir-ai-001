---
name: career-scout
description: Find and score jobs for Sakir in Bangladesh and abroad, and write tailored CVs and cover letters from his master CV. Use for "/jobs", "find jobs", "/cv <job>", "cover letter", and the weekly Monday 10:00 job scan.
---
# Career scout

## Sources of truth
- `/knowledge/career/cv-master.md` and `/knowledge/me/profile.md` — the ONLY facts allowed in a CV.
- `/knowledge/me/goals.md` — target roles, locations, salary.

## Weekly scan (Monday 10:00)
1. Search the web for roles posted in the last 7 days matching goals.md:
   Lead / Principal / Staff Engineer, Software Architect, Engineering Manager,
   Head of Engineering, CTO — Bangladesh (bdjobs, LinkedIn) and remote/international.
2. Open each posting; skip expired, unclear or agency spam.
3. Score fit 0–100: skills match (40), seniority (25), location/remote (15),
   company quality (10), salary if shown (10).
4. Save to `/outbox/career/<YYYY-MM-DD>-jobs.md` as a table: #, role, company,
   location, score, link, one-line why.
5. Send Sakir the top 10 with scores and links.

## Tailored CV (`/cv <number>`)
1. Read the job posting again.
2. Write `/outbox/career/<company>-<role>/cv.md` and `cover-letter.md`:
   - reorder and reword experience to match the posting's needs
   - use only facts from cv-master.md; mark any missing number as [ADD NUMBER]
   - cover letter 200–250 words, specific to the company
3. Send Sakir the file paths and 3 bullet points on what you emphasised.

## Never
- Never apply, submit forms or email recruiters. Sakir applies himself.
- Never mention Grameenphone/eGeneration internal details beyond the CV text.
