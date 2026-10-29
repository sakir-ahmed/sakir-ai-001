# Sakir AI knowledge base

These Markdown files are the single source of truth for every agent. Edit them
directly (on the server or on GitHub from your phone), then run
`sakir-ai reindex`, or wait for the nightly re-index at 02:30.

| Folder | Used by | Notes |
| --- | --- | --- |
| `me/` | all writing agents, career, branding | who Sakir is, voice, likes/dislikes, goals |
| `datatech/` | sales, content | `company.md` facts and contact, `brand.md` marketing identity, `case-studies.md` public results |
| `products/<product>/` | sales, content | one folder per product; `dt-restora` first |
| `sales/` | sales pipeline | reply and classifier prompts, FAQ templates, playbook, objections, Banglish glossary |
| `servers/` | DevOps agent | what runs where and what "healthy" means |
| `career/` | career agent | master CV with every achievement |
| `inbox/` | you | `/remember` notes from Hermes; move them into the right file |

Rules
- Never put passwords, tokens or client contracts here.
- Anything marked `TODO` is unknown. Files with `TODO` in prices are never used
  for automatic replies; FAQ templates containing `TODO` are ignored.
- Keep facts short and specific: numbers, names, prices in ৳.
