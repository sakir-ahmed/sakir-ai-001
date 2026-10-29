#!/usr/bin/env bash
# =============================================================================
# Sakir AI 001 — install AI coding tools on the server (optional)
#
# Installs, for the admin user (default: sakir), the command-line AI tools
# Sakir can open over SSH to set up, fix or extend the server:
#
#   claude   Claude Code (Anthropic)     reads CLAUDE.md  -> AGENTS.md
#   codex    OpenAI Codex CLI            reads AGENTS.md
#   grok     xAI Grok Build CLI          reads AGENTS.md / CLAUDE.md
#   gemini   Google Gemini CLI           reads GEMINI.md  -> AGENTS.md
#
# Every tool follows the same rules in AGENTS.md at the repo root, so whichever
# one Sakir opens works the same way.
#
# Usage:
#   sudo bash scripts/install-ai-tools.sh                 # asks for each tool
#   sudo bash scripts/install-ai-tools.sh --all
#   sudo bash scripts/install-ai-tools.sh --claude --codex
#   ADMIN_USER=sakir sudo -E bash scripts/install-ai-tools.sh --grok
#
# Tools are installed per user (in ~/.local/bin or the user's npm prefix),
# never with `sudo npm -g`, and never for root. Logging in is done by Sakir
# afterwards; this script never asks for or stores any key (see the end).
# =============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "${SCRIPT_DIR}/../lib/common.sh"
# shellcheck disable=SC2034  # read by the logging helpers in lib/common.sh
LOG_FILE=/var/log/sakir-ai-tools.log

: "${ADMIN_USER:=sakir}"
: "${NODE_MAJOR:=22}"

# ---- choose tools ---------------------------------------------------------------
want_claude=0 want_codex=0 want_grok=0 want_gemini=0 asked=$#
while (($#)); do
  case "$1" in
    --all) want_claude=1 want_codex=1 want_grok=1 want_gemini=1 ;;
    --claude) want_claude=1 ;;
    --codex) want_codex=1 ;;
    --grok) want_grok=1 ;;
    --gemini) want_gemini=1 ;;
    -h|--help) awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
    *) die "Unknown option: $1 (see --help)" ;;
  esac
  shift
done

require_root
id "$ADMIN_USER" >/dev/null 2>&1 || die "User '$ADMIN_USER' does not exist (run install.sh --step admin first)."
USER_HOME="$(getent passwd "$ADMIN_USER" | cut -d: -f6)"

# Runs a command as the admin user with a login-like environment.
as_user() { sudo -u "$ADMIN_USER" -H bash -lc "$*"; }

if ((asked == 0)); then
  confirm "Install Claude Code (needs a Claude Pro/Max/Team account or an API key)?" && want_claude=1
  confirm "Install OpenAI Codex CLI (needs a ChatGPT plan or an OpenAI API key)?" && want_codex=1
  confirm "Install xAI Grok Build CLI (needs an xAI/Grok account or an xAI API key)?" && want_grok=1
  confirm "Install Google Gemini CLI (needs a Google account or a Gemini API key)?" && want_gemini=1
fi
(( want_claude + want_codex + want_grok + want_gemini > 0 )) || { info "Nothing selected."; exit 0; }

# ---- common requirements -----------------------------------------------------------
section "Base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y -q
apt-get install -y -q --no-install-recommends curl ca-certificates git ripgrep gnupg

# ~/.local/bin on PATH for login shells (native installers put binaries there).
PROFILE="${USER_HOME}/.profile"
if ! grep -q 'sakir-ai: local bin' "$PROFILE" 2>/dev/null; then
  cat >> "$PROFILE" <<'EOF'

# sakir-ai: local bin and per-user npm packages for AI coding tools
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"
EOF
  chown "$ADMIN_USER:" "$PROFILE"
fi

# Node.js is needed only for Gemini CLI (npm package).
install_node() {
  if command -v node >/dev/null && (( $(node -p 'process.versions.node.split(".")[0]') >= NODE_MAJOR )); then
    info "Node.js $(node --version) already installed"
    return
  fi
  section "Node.js ${NODE_MAJOR} (NodeSource repository)"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
    | gpg --dearmor --yes -o /etc/apt/keyrings/nodesource.gpg
  echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" \
    > /etc/apt/sources.list.d/nodesource.list
  apt-get update -y -q
  apt-get install -y -q nodejs
  # Per-user global prefix, so no tool is ever installed with sudo npm -g.
  as_user 'mkdir -p ~/.npm-global && npm config set prefix ~/.npm-global'
  ok "Node.js $(node --version)"
}

# ---- tools ------------------------------------------------------------------------
installed=()

if ((want_claude)); then
  section "Claude Code (Anthropic native installer)"
  as_user 'curl -fsSL https://claude.ai/install.sh | bash'
  as_user 'claude --version' && installed+=("claude")
fi

if ((want_codex)); then
  section "OpenAI Codex CLI (official installer)"
  as_user 'curl -fsSL https://chatgpt.com/codex/install.sh | sh'
  as_user 'codex --version' && installed+=("codex")
fi

if ((want_grok)); then
  section "xAI Grok Build CLI (official installer)"
  as_user 'curl -fsSL https://x.ai/cli/install.sh | bash'
  as_user 'export PATH="$HOME/.grok/bin:$PATH"; grok --version' && installed+=("grok")
  if ! grep -q '.grok/bin' "$PROFILE"; then
    echo 'export PATH="$HOME/.grok/bin:$PATH"' >> "$PROFILE"
  fi
fi

if ((want_gemini)); then
  install_node
  section "Google Gemini CLI (npm, per user)"
  as_user 'npm install -g @google/gemini-cli'
  as_user 'gemini --version' && installed+=("gemini")
fi

# ---- clone the repo for the tools to work in -------------------------------------
REPO_DIR="${USER_HOME}/sakir-ai-001"
if [[ ! -d "${REPO_DIR}/.git" ]]; then
  section "Clone sakir-ai-001 for the AI tools"
  as_user "git clone https://github.com/sakir-ahmed/sakir-ai-001 '${REPO_DIR}'" \
    || warn "Clone failed (private repo?). Clone it yourself as ${ADMIN_USER} into ${REPO_DIR}."
fi

# ---- next steps ---------------------------------------------------------------------
section "Done"
ok "Installed for ${ADMIN_USER}: ${installed[*]:-none}"
cat <<EOF

  Log in once as ${ADMIN_USER} (open a NEW SSH session so PATH is updated):

    cd ~/sakir-ai-001
    claude                       # shows a login URL; open it on your laptop or phone
    codex login --device-auth    # prints a code + URL for headless servers
    grok login --device-auth     # prints a code + URL for headless servers
    gemini                       # choose "Login with Google" and follow the link

  Then start any tool inside ~/sakir-ai-001 and say, for example:
    "Read AGENTS.md, then run sakir-ai health and fix what fails."

  Rules for all tools are in AGENTS.md. Subscriptions or API keys are your own
  accounts; nothing was stored by this script. Details: docs/AI-TOOLS.md
EOF
