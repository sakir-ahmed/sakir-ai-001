---
name: sales-desk
description: Answer Sakir's questions about leads, customer messages, drafts waiting, sales numbers and model spend; pause or resume automatic customer replies. Use for "/lead", "leads", "inbox", "sales", "pause sales", "resume sales".
---
# Sales desk (read side)

Customer replies are handled by dt-assistant and approved in @DTSalesDesk_bot.
You read its data and can pause it; you never message customers yourself.

| Sakir asks | Run |
| --- | --- |
| How are sales / today's numbers | `python3 /opt/sakir-tools/sakir.py sales summary --days 1` (or `--days 7`) |
| Find a lead | `python3 /opt/sakir-tools/sakir.py sales leads <name, business or phone>` |
| What is waiting for me | `python3 /opt/sakir-tools/sakir.py sales inbox` |
| How much did AI cost | `python3 /opt/sakir-tools/sakir.py sales spend` |
| Stop automatic replies | `python3 /opt/sakir-tools/sakir.py sales pause` |
| Start them again | `python3 /opt/sakir-tools/sakir.py sales resume` |

## Answer style
- Lead summary: name · business · phone · stage · last message time.
- Remind Sakir that approvals happen in @DTSalesDesk_bot (buttons on each draft).
- If a lead is outside Meta's 24-hour window and has a phone number, suggest a call
  or WhatsApp.

## Lead stages
new → interested → demo → proposal → won / lost.
