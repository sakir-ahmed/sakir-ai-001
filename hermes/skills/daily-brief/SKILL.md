---
name: daily-brief
description: Morning brief (08:30) and evening summary (21:30) for Sakir covering sales, approvals, server health, content and spend. Use for "brief", "/brief", "summary", "how is everything", and for the scheduled daily runs.
---
# Daily brief

## Gather (run these; skip any that fail and say which)
```bash
T=/opt/sakir-tools/sakir.py
python3 $T sales summary --days 1     # leads, messages, approvals, spend
python3 $T sales inbox                # drafts waiting
python3 $T server status              # containers
python3 $T server errors              # error lines per container, last hour
python3 $T server disk                # disk and memory
python3 $T server reboot-check        # security updates waiting for a reboot?
python3 $T content calendar --days 2  # posts today/tomorrow
python3 $T sales spend                # model spend vs limit
```

## Write the brief (Telegram, max ~15 lines)
Morning title: "Good morning — <weekday, date>". Evening: "Today in numbers".

1. **Needs you** (only if any): drafts waiting (count, oldest age), failed posts,
   unhealthy containers, disk over 80%, spend over 70% of limit, approvals pending,
   reboot pending (suggest a quiet time, e.g. 04:00, and offer to start the reboot request).
2. **Sales**: new leads, messages in, replies (auto/approved/edited), leads by stage.
3. **Servers**: "All healthy" or the problems in one line each.
4. **Content**: posts published / scheduled next.
5. **Spend**: $X of $Y this month.
6. Evening only: one suggestion for tomorrow based on the numbers.

Rules: no tables, numbers first, plain words. If everything is fine say so in one line.

## Schedule (set once, by asking Hermes)
- Every day at 08:30 Asia/Dhaka: run daily-brief (morning).
- Every day at 21:30 Asia/Dhaka: run daily-brief (evening).
