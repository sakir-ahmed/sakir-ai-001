# Telegram bot naming and migration

This runbook tracks the requested naming change without claiming a live cutover.
Use `sakir_ai_001_<role>_bot` for additional roles; the main bot is
`sakir_ai_001_bot`. Keep the customer-facing identity Datatech BD Assistant.
`config/telegram-bots.yaml` records the naming targets, not runtime credentials.

| Role | Legacy username | Target username | Status |
| --- | --- | --- | --- |
| Hermes private assistant | @SakirAI_bot | @sakir_ai_001_bot | Replacement created in prior BotFather session; runtime migration pending |
| Sales approvals | @DTSalesDesk_bot | @sakir_ai_001_sales_bot | Creation submitted in prior session; completion and runtime migration unverified |
| Existing alerts | @SakirAlertBoxBot | @SakirAlertBoxBot | Protected; retain unchanged |

Telegram usernames cannot be changed after bot creation. A replacement has a
different identity and token. Existing Git history, dated verification records,
and the original blueprint retain their historical names. Current installer,
operator instructions, UI labels and skill references use the target names.

## Cutover checklist

- [ ] Verify both replacement identities in BotFather.
- [ ] Run `sakir-ai backup` and verify completion.
- [ ] Owner privately enters replacement credentials using the existing settings
  interface or `install.sh --step secrets`; never paste tokens into chat or Git.
  Main credentials must agree in `data/hermes/.env` and `secrets/safe-exec.env`;
  sales credentials belong in `secrets/dt-assistant.env`.
- [ ] Obtain approval before recreating affected containers, as AGENTS.md requires.
- [ ] Activate Hermes, safe-exec and dt-assistant with their new credentials.
- [ ] Start both new bots from the owner's Telegram account.
- [ ] Verify main text reply and safe-exec notification; verify sales `/inbox`
  and approval buttons with a synthetic draft. Preserve owner ID restrictions.
- [ ] Update actual live monitoring integrations that used the legacy main token.
- [ ] Record verification evidence and deployment revision in PROGRESS.md.
- [ ] List all remaining owned bots, review external dependencies, and obtain
  action-time confirmation immediately before permanent deletion. Exclude both
  replacements and @SakirAlertBoxBot. No old bot has been deleted by this change.

Keep legacy bots available until the cutover passes. Retain encrypted backup and
existing conversation/memory data; deleting a Telegram bot is irreversible.
