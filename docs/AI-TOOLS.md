# AI coding tools on the server

Sakir can open any of these AI tools over SSH and ask it to set up, fix or extend
the server. All of them follow the same rules in [`AGENTS.md`](../AGENTS.md).

| Tool | Command | Company | Account it uses | Reads |
| --- | --- | --- | --- | --- |
| Claude Code | `claude` | Anthropic | Claude Pro/Max/Team, or an Anthropic API key | `CLAUDE.md` → `AGENTS.md` |
| Codex CLI | `codex` | OpenAI | ChatGPT plan, or an OpenAI API key | `AGENTS.md` |
| Grok Build | `grok` | xAI | Grok/xAI account, or `XAI_API_KEY` | `AGENTS.md`, `CLAUDE.md` |
| Gemini CLI | `gemini` | Google | Google account, or a Gemini API key | `GEMINI.md` → `AGENTS.md` |

These are different from the models inside Sakir AI 001 (Hermes and dt-assistant use
OpenRouter keys). A ChatGPT or Claude subscription pays for these CLIs only; it does not
pay for the OpenRouter API usage of the agents.

## Install

During the main install, the optional `aitools` step asks which tools to install.
Later, at any time:

```bash
sudo bash /opt/sakir-ai/scripts/install-ai-tools.sh            # asks for each tool
sudo bash /opt/sakir-ai/scripts/install-ai-tools.sh --all
sudo bash /opt/sakir-ai/scripts/install-ai-tools.sh --codex --grok
```

The script installs each tool for the `sakir` user with its official installer
(Claude Code, Codex and Grok native installers; Gemini via npm with Node.js 22),
puts them on `PATH`, and clones this repo to `~/sakir-ai-001`. It never runs a tool
as root and never asks for or stores a key.

## Log in once (headless server)

Open a **new** SSH session as `sakir` (so `PATH` is updated), then:

```bash
cd ~/sakir-ai-001
claude                       # prints a login link; open it on your laptop or phone
codex login --device-auth    # prints a code and a link
grok login --device-auth     # prints a code and a link
gemini                       # choose "Login with Google" and open the link
```

## Using them

Always start the tool inside `~/sakir-ai-001` so it reads `AGENTS.md`:

```bash
cd ~/sakir-ai-001 && codex          # or: claude / grok / gemini
```

Good first requests:
- "Read AGENTS.md and docs/ARCHITECTURE.md, then run `sakir-ai health` and explain what fails."
- "Add the backup hook for the DT Restora database in scripts/backup.d/, test it, and commit on a branch."
- "Update n8n to the newest version following docs/OPERATIONS.md → Updating."
- "Why is dt-assistant unhealthy? Check `sakir-ai logs dt-assistant` and propose a fix."

## Safety

- Keep each tool in its **ask-before-acting** (default) mode for anything that changes the
  server. Use auto-approve modes only inside the repo for code edits and tests.
- `AGENTS.md` tells every tool to ask you before reboot, deletes, database drops, firewall
  or SSH changes, and to run `sakir-ai backup` first.
- Tools run as `sakir`, who has `sudo`. Read what a tool wants to run with `sudo` before
  you approve it.
- Never paste secrets into a tool's chat. If a tool needs a value, put it in the right file
  with `sudo bash /opt/sakir-ai/install.sh --step secrets`.
- Code changes go through Git: the tool commits on a branch in `~/sakir-ai-001`; deploy with
  `sudo bash install.sh --step layout && sudo bash install.sh --step stack`.

## Update or remove

| Tool | Update | Remove |
| --- | --- | --- |
| Claude Code | updates itself (or `claude update`) | `rm -f ~/.local/bin/claude && rm -rf ~/.local/share/claude` |
| Codex | re-run its installer | see `codex --help` / the Codex docs |
| Grok Build | re-run its installer | `rm -rf ~/.grok` |
| Gemini CLI | `npm install -g @google/gemini-cli@latest` | `npm uninstall -g @google/gemini-cli` |

Sources: [Claude Code setup](https://code.claude.com/docs/en/setup),
[Codex CLI on Linux](https://tecmint.com/openai-codex-cli-linux),
[Grok Build install](https://codersera.com/blog/how-to-install-grok-build-cli-2026/),
[Grok Build project rules](https://docs.x.ai/build/features/project-rules),
[Gemini CLI](https://google-gemini.github.io/gemini-cli).
