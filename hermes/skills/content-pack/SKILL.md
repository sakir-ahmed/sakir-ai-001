---
name: content-pack
description: Create a marketing pack for a Datatech BD product (social posts, reel scripts, LinkedIn post, SEO page, product-book outline) in Bangla and English, and schedule approved posts. Use for "/post <product> <topic>", "make posts", "marketing", "content", "schedule post".
---
# Content pack

## 1. Load facts
- `sakir-persona`, then `/knowledge/datatech/company.md` and `/knowledge/datatech/brand.md`
  (tagline, colours, hashtags, approved call-to-action lines, links)
- `/knowledge/datatech/case-studies.md` for customer stories (only clients marked public)
- `/knowledge/products/dt-<product>/features.md`, `pricing.md`, `faq.md`
- Optional: `python3 /opt/sakir-tools/sakir.py kb search <product> "<topic>"`

If pricing.md still contains TODO, do not mention prices; tell Sakir.

## 2. Write (save every file under /outbox/<product>/<YYYY-MM-DD>-<topic-slug>/)
| File | Content |
| --- | --- |
| `facebook-1.md` … `facebook-3.md` | hook line, 3 benefits, price line (only from pricing.md), call to action ("Inbox করুন / free demo"); Bangla first, English below |
| `reel-1.md`, `reel-2.md` | 30-second scripts: scene, on-screen text, voice line, per 5-second beat |
| `linkedin.md` | business-owner angle, English, 120–200 words, no hashtags spam (max 3) |
| `seo-page.md` | title ≤ 60 chars, meta description ≤ 155, H1, 4–6 sections, FAQ (5 Q&A), slug |
| `product-book-outline.md` | chapter list for the Bangla/English PDF product book with screenshot placeholders |

Rules: never invent features or prices; Bangla in natural, polite language;
one clear call to action per post.

## 3. Show Sakir
Send a short summary: folder path, the 3 post hooks, and ask which to schedule and when.

## 4. Schedule ONLY after Sakir approves
For each approved post and platform (facebook, instagram, linkedin, youtube, tiktok, x):
```bash
python3 /opt/sakir-tools/sakir.py content schedule --product restora --platform facebook \
  --at "2026-11-05 19:30" --caption-file /outbox/restora/2026-11-04-launch/facebook-1.md \
  --media /outbox/restora/2026-11-04-launch/post-1.png
```
- Facebook and Instagram are posted automatically at that time (Instagram needs an image).
- Other platforms: Sakir gets a ready-to-paste reminder at that time.
- Best Bangladesh posting times: 13:00–14:00 and 19:30–22:00.

Check with `python3 /opt/sakir-tools/sakir.py content calendar --days 7`.
