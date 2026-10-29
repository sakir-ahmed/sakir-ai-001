# Privacy policy — template for datatechbd.com

> **Template, not legal advice.** Fill the `[brackets]`, check it against current
> Bangladeshi law and Meta's Platform Terms, and have it reviewed if you can.
> Meta app review needs a public URL to this page (e.g. https://datatechbd.com/privacy)
> and a data-deletion URL (the "Deleting your data" section can serve as that page).
> Keep the retention periods here equal to `retention:` in `config/dt-assistant.yaml`.

---

# Privacy Policy

**Datatech BD Ltd.** · Last updated: [date]

Datatech BD Ltd. ("we", "us") is a software company registered in Bangladesh
(RJSC). This policy explains what we collect when you contact us on Facebook,
Messenger, Instagram or our website, and how we use it.

## Who answers your messages
Messages to our Facebook Page and Instagram account are first answered by
**Datatech BD Assistant**, an automated assistant. Replies about prices, orders,
complaints and anything unusual are checked or written by a person on our team.
You can ask to talk to a person at any time.

## What we collect
- Your name and profile ID as provided by Facebook or Instagram
- The messages and comments you send us, including voice messages
- Details you choose to share: phone number, business name, what you need
- Basic technical logs of our servers (time, IP address) for security

We do not collect payment card details through Messenger or Instagram.

## Why we use it
- To answer your questions, give demos and send you proposals you asked for
- To follow up once about a conversation you started
- To improve our answers (we review a sample of conversations)
- To keep our systems secure

We do **not** sell your data or use it for advertising outside our own Page.

## Service providers
To run the assistant we use: Meta (Facebook/Instagram messaging), OpenRouter and the
AI model providers it routes to (to understand and draft replies), and our own server at
[hosting provider, country]. They receive only what is needed to provide the service.
Message text sent to AI providers is used to produce a reply, not to identify you.

## How long we keep it
- Message content: up to **12 months**, then deleted automatically
- Contact details of people who did not become customers: up to **12 months** after the last message
- Customer records: for as long as you use our products and as required by law
- Server security logs: up to **30 days**
- Encrypted backups: up to **14 days**

## Your choices
- Ask what we hold about you, ask us to correct it, or ask us to delete it
- Ask us to stop follow-up messages

## Deleting your data
Send "DELETE MY DATA" to our Facebook Page, or email [privacy email] with your name and
Facebook/Instagram profile name. We delete your messages and contact details within
**[30] days** and confirm by reply. Backups containing them expire within 14 days after that.

## Contact
Datatech BD Ltd., [address], Bangladesh · [privacy email] · [phone]

---

## For Sakir: handling a deletion request
1. Find the lead: in @DTSalesDesk_bot `/lead <name>`.
2. Delete (asks for confirmation on the server; take a backup first):
   ```bash
   sakir-ai backup
   docker compose -f /opt/sakir-ai/compose.yml exec ai-db \
     psql -U sakirai -d sakirai -c "DELETE FROM leads WHERE id = <id>;"
   ```
   Messages and drafts of that lead are deleted with it (cascade).
3. Reply to the person that it is done.
