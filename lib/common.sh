#!/usr/bin/env bash
# =============================================================================
# Sakir AI 001 — shared helpers for install.sh and the scripts in scripts/
#
# Sourced, never executed directly. Provides:
#   - coloured, timestamped logging that is also written to the install log
#   - small guards (require_root, require_cmd)
#   - idempotency markers so every install step can be re-run safely
#   - helpers to read/write KEY=VALUE secret files without leaking values
# =============================================================================

# ---- Locations ---------------------------------------------------------------
# INSTALL_DIR can be overridden before sourcing (useful for testing).
: "${INSTALL_DIR:=/opt/sakir-ai}"
: "${STATE_DIR:=${INSTALL_DIR}/.state}"
: "${LOG_FILE:=/var/log/sakir-ai-install.log}"

# ---- Logging -----------------------------------------------------------------
# Colours only when writing to a terminal, so log files stay clean.
if [[ -t 1 ]]; then
  C_RESET=$'\e[0m'; C_BLUE=$'\e[34m'; C_GREEN=$'\e[32m'
  C_YELLOW=$'\e[33m'; C_RED=$'\e[31m'; C_BOLD=$'\e[1m'
else
  C_RESET=""; C_BLUE=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_BOLD=""
fi

_log() {
  # $1 = level label, $2 = colour, rest = message
  local level="$1" colour="$2"; shift 2
  local ts; ts="$(date '+%Y-%m-%d %H:%M:%S')"
  printf '%s %s[%s]%s %s\n' "$ts" "$colour" "$level" "$C_RESET" "$*"
  # Plain copy for the log file (ignore errors if the log is not writable yet).
  printf '%s [%s] %s\n' "$ts" "$level" "$*" >> "$LOG_FILE" 2>/dev/null || true
}
info()  { _log INFO  "$C_BLUE"   "$@"; }
ok()    { _log OK    "$C_GREEN"  "$@"; }
warn()  { _log WARN  "$C_YELLOW" "$@"; }
error() { _log ERROR "$C_RED"    "$@"; }
die()   { error "$@"; exit 1; }

# Prints a bold section banner for each install step.
section() {
  printf '\n%s==> %s%s\n' "$C_BOLD" "$*" "$C_RESET"
  printf '\n==> %s\n' "$*" >> "$LOG_FILE" 2>/dev/null || true
}

# ---- Guards ------------------------------------------------------------------
require_root() {
  [[ $EUID -eq 0 ]] || die "Run this as root: sudo bash $0"
}

require_cmd() {
  local cmd
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || die "Required command not found: $cmd"
  done
}

# ---- Idempotency markers -------------------------------------------------------
# A step writes a marker when it finishes; re-runs skip finished steps unless
# --force is given. Markers live in $STATE_DIR/<step>.done
step_done()  { [[ -f "${STATE_DIR}/$1.done" ]]; }
mark_done()  { mkdir -p "$STATE_DIR"; date -Is > "${STATE_DIR}/$1.done"; }
clear_mark() { rm -f "${STATE_DIR}/$1.done"; }

# ---- Secret / env file helpers ---------------------------------------------------
# Files are KEY=VALUE, one per line, mode 600, owner root. Values are never echoed.

# env_get FILE KEY  -> prints the value (empty if missing)
env_get() {
  local file="$1" key="$2"
  [[ -f "$file" ]] || return 0
  # Take the last definition; strip optional surrounding quotes.
  # `|| true`: a missing key is normal and must not trip `set -e -o pipefail`.
  { grep -E "^${key}=" "$file" || true; } | tail -n1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'
}

# env_set FILE KEY VALUE -> adds or replaces KEY in FILE (atomic, keeps mode 600)
env_set() {
  local file="$1" key="$2" value="$3" tmp
  mkdir -p "$(dirname "$file")"
  touch "$file"; chmod 600 "$file"
  tmp="$(mktemp "${file}.XXXX")"
  grep -vE "^${key}=" "$file" > "$tmp" || true
  printf '%s=%s\n' "$key" "$value" >> "$tmp"
  chmod 600 "$tmp"
  mv "$tmp" "$file"
}

# env_ensure FILE KEY VALUE -> sets KEY only if it is missing or empty
env_ensure() {
  local file="$1" key="$2" value="$3"
  if [[ -z "$(env_get "$file" "$key")" ]]; then
    env_set "$file" "$key" "$value"
  fi
}

# Random secret: 48 hex characters (192 bits). Safe in URLs and env files.
gen_secret() { openssl rand -hex 24; }

# ---- Prompts ---------------------------------------------------------------------
# ask VAR "Question" "default"  -> reads a visible answer into VAR
# In non-interactive mode the default (or an existing value) is used silently.
ask() {
  local __var="$1" question="$2" default="${3:-}" answer=""
  if [[ "${NON_INTERACTIVE:-0}" == "1" ]]; then
    printf -v "$__var" '%s' "$default"; return 0
  fi
  if [[ -n "$default" ]]; then
    read -r -p "  ${question} [${default}]: " answer </dev/tty || true
  else
    read -r -p "  ${question}: " answer </dev/tty || true
  fi
  printf -v "$__var" '%s' "${answer:-$default}"
}

# ask_secret VAR "Question" -> reads a hidden answer; empty keeps the old value
ask_secret() {
  local __var="$1" question="$2" answer=""
  if [[ "${NON_INTERACTIVE:-0}" == "1" ]]; then
    printf -v "$__var" '%s' ""; return 0
  fi
  read -r -s -p "  ${question} (hidden, Enter to skip): " answer </dev/tty || true
  echo
  printf -v "$__var" '%s' "$answer"
}

# confirm "Question" -> returns 0 for yes. Defaults to "no".
confirm() {
  local answer=""
  [[ "${NON_INTERACTIVE:-0}" == "1" ]] && return 1
  read -r -p "  $1 [y/N]: " answer </dev/tty || true
  [[ "$answer" =~ ^[Yy]([Ee][Ss])?$ ]]
}

# ---- Misc ------------------------------------------------------------------------
# Public IPv4 of this server (used to check DNS before requesting certificates).
public_ip() {
  curl -fsS4 --max-time 5 https://api.ipify.org 2>/dev/null \
    || curl -fsS4 --max-time 5 https://ifconfig.me 2>/dev/null \
    || hostname -I | awk '{print $1}'
}

# Runs docker compose from the install directory.
dc() { (cd "$INSTALL_DIR" && docker compose "$@"); }

# ---- Alerts ----------------------------------------------------------------------
# notify_telegram "text" -> sends a message to Sakir with the @SakirAI_bot token
# stored for safe-exec. Never fails the caller (alerts must not break scripts).
notify_telegram() {
  local f="${INSTALL_DIR}/secrets/safe-exec.env" token owner
  token="$(env_get "$f" TELEGRAM_BOT_TOKEN)"
  owner="$(env_get "$f" TELEGRAM_OWNER_ID)"
  [[ -n "$token" && -n "$owner" ]] || { warn "Telegram not configured; alert not sent: $1"; return 0; }
  # The token goes in the URL; curl reads it from stdin config so it never shows in `ps`.
  printf 'url = "https://api.telegram.org/bot%s/sendMessage"\n' "$token" \
    | curl -fsS --max-time 15 -K - \
        --data-urlencode "chat_id=${owner}" \
        --data-urlencode "text=[$(hostname)] $1" >/dev/null 2>&1 \
    || warn "Telegram alert failed: $1"
  return 0
}

# hc_ping KEY [suffix] -> pings an optional Healthchecks.io-style URL stored in
# .env under KEY (e.g. HC_BACKUP_URL). suffix: "" = success, "/start", "/fail".
# Outside monitors alert Sakir when an expected ping does NOT arrive, which also
# covers "the whole server is down" (something an on-server monitor cannot report).
hc_ping() {
  local url; url="$(env_get "${INSTALL_DIR}/.env" "$1")"
  [[ -n "$url" ]] || return 0
  curl -fsS --max-time 10 --retry 3 -o /dev/null "${url}${2:-}" || true
}
