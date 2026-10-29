#!/usr/bin/env bash
# =============================================================================
# Sakir AI 001 — installer for a fresh Ubuntu 22.04 / 24.04 server
#
# What it does (each step is idempotent and can be re-run on its own):
#   preflight   check OS, CPU architecture, RAM, disk, internet
#   system      packages, timezone, swap, automatic security updates
#   admin       admin user + SSH hardening (never locks you out, see notes)
#   firewall    UFW: only SSH, HTTP, HTTPS open; fail2ban for SSH
#   docker      Docker Engine + Compose from Docker's official apt repository
#   layout      copy this bundle to /opt/sakir-ai and create folders
#   secrets     ask for tokens/keys, generate passwords, write secrets/*.env
#   knowledge   create the knowledge Git repo from the templates
#   nginx       public reverse proxy: Meta webhook, n8n webhooks, media
#   tls         Let's Encrypt certificate (only if DNS already points here)
#   hostops     root runner for allowlisted host actions (reboot, nginx, ssl)
#   stack       build images and start all containers except Hermes
#   hermes      Hermes Agent setup wizard, skills, start
#   timers      nightly backup and knowledge re-index (systemd timers)
#   tailscale   private admin access to n8n, Grafana, Uptime Kuma (optional)
#   aitools     Claude Code, Codex, Grok Build, Gemini CLI for the admin user (optional)
#   verify      health check of everything
#
# Usage:
#   sudo bash install.sh                 run every step not yet done
#   sudo bash install.sh --step secrets  run one step (even if done before)
#   sudo bash install.sh --from stack    run this step and every step after it
#   sudo bash install.sh --list          list steps and whether they are done
#   sudo bash install.sh --non-interactive  use defaults, skip questions
#
# Log: /var/log/sakir-ai-install.log
# =============================================================================
set -Eeuo pipefail

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${BUNDLE_DIR}/lib/common.sh"

trap 'error "Failed at line ${LINENO}: ${BASH_COMMAND}. See ${LOG_FILE}"' ERR

STEPS=(preflight system admin firewall docker layout secrets knowledge nginx tls hostops stack hermes timers tailscale aitools verify)

# Settings that can be overridden with environment variables.
: "${ADMIN_USER:=sakir}"            # Linux admin account to create
: "${TIMEZONE:=Asia/Dhaka}"
: "${SWAP_SIZE_GB:=8}"
: "${NON_INTERACTIVE:=0}"

# =============================================================================
# Step: preflight
# =============================================================================
step_preflight() {
  section "Preflight checks"
  require_root

  # shellcheck disable=SC1091
  . /etc/os-release
  [[ "${ID}" == "ubuntu" ]] || die "This installer supports Ubuntu only (found ${ID})."
  case "${VERSION_ID}" in
    22.04|24.04) ok "Ubuntu ${VERSION_ID} detected" ;;
    *) warn "Ubuntu ${VERSION_ID} is untested; 22.04 or 24.04 LTS is recommended." ;;
  esac

  local arch; arch="$(dpkg --print-architecture)"
  [[ "$arch" == "amd64" || "$arch" == "arm64" ]] || die "Unsupported architecture: $arch"

  local mem_gb disk_gb
  mem_gb=$(( $(awk '/MemTotal/ {print $2}' /proc/meminfo) / 1024 / 1024 ))
  disk_gb=$(( $(df --output=avail -k / | tail -1) / 1024 / 1024 ))
  info "RAM: ${mem_gb} GB, free disk on /: ${disk_gb} GB"
  (( mem_gb >= 8 ))  || die "At least 8 GB RAM is needed (16+ recommended)."
  (( disk_gb >= 40 )) || die "At least 40 GB free disk is needed."

  # Minimal images may lack curl; it is needed before the system step.
  command -v curl >/dev/null || { apt-get update -y && apt-get install -y curl ca-certificates; }
  curl -fsS --max-time 10 https://download.docker.com >/dev/null \
    || die "No internet access to download.docker.com."
  ok "Preflight passed"
}

# =============================================================================
# Step: system
# =============================================================================
step_system() {
  section "System packages, timezone, swap, security updates"
  export DEBIAN_FRONTEND=noninteractive

  apt-get update -y
  apt-get upgrade -y
  apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg lsb-release apt-transport-https \
    ufw fail2ban unattended-upgrades \
    jq git rsync openssl age rclone \
    nginx certbot python3-certbot-nginx \
    htop ncdu dnsutils

  # Timezone: the schedules (backups 03:00, briefs 08:30) use local time.
  timedatectl set-timezone "$TIMEZONE"
  ok "Timezone set to $TIMEZONE"

  # Swap file: protects the DT products and the AI stack from sudden OOM kills.
  if ! swapon --show | grep -q '/swapfile'; then
    fallocate -l "${SWAP_SIZE_GB}G" /swapfile
    chmod 600 /swapfile
    mkswap /swapfile >/dev/null
    swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    ok "Swap of ${SWAP_SIZE_GB} GB enabled"
  else
    info "Swap already present"
  fi
  # Prefer RAM; use swap only under pressure.
  cat > /etc/sysctl.d/90-sakir-ai.conf <<'EOF'
# Sakir AI 001: use swap only when memory is really short
vm.swappiness = 10
# Allow more inotify watchers (Docker, log shippers)
fs.inotify.max_user_watches = 524288
EOF
  sysctl --system >/dev/null

  # Automatic security updates (no automatic reboot; Sakir decides reboots).
  cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
  ok "Automatic security updates enabled"
}

# =============================================================================
# Step: admin  (create admin user, harden SSH without locking anyone out)
# =============================================================================
step_admin() {
  section "Admin user and SSH hardening"

  if ! id "$ADMIN_USER" >/dev/null 2>&1; then
    adduser --disabled-password --gecos "Sakir AI admin" "$ADMIN_USER"
    ok "User $ADMIN_USER created"
  fi
  usermod -aG sudo "$ADMIN_USER"

  # Copy root's SSH keys to the admin user if the admin user has none yet.
  local home="/home/${ADMIN_USER}"
  if [[ -s /root/.ssh/authorized_keys && ! -s "${home}/.ssh/authorized_keys" ]]; then
    install -d -m 700 -o "$ADMIN_USER" -g "$ADMIN_USER" "${home}/.ssh"
    install -m 600 -o "$ADMIN_USER" -g "$ADMIN_USER" /root/.ssh/authorized_keys "${home}/.ssh/authorized_keys"
    ok "Copied root's SSH keys to ${ADMIN_USER}"
  fi

  if [[ ! -s "${home}/.ssh/authorized_keys" ]]; then
    warn "No SSH key found for ${ADMIN_USER}."
    warn "Password login stays ON so you are not locked out."
    warn "On your laptop run:  ssh-copy-id ${ADMIN_USER}@<server-ip>"
    warn "Then re-run:         sudo bash install.sh --step admin"
    # Still give the admin user a password so sudo works; ask for it once.
    if ! passwd -S "$ADMIN_USER" | grep -q ' P '; then
      info "Set a password for ${ADMIN_USER} (needed for sudo):"
      passwd "$ADMIN_USER" </dev/tty
    fi
    return 0   # do not mark done: re-run once a key exists
  fi

  # Key exists: allow sudo without password for the admin (key-only login).
  echo "${ADMIN_USER} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-${ADMIN_USER}"
  chmod 440 "/etc/sudoers.d/90-${ADMIN_USER}"
  visudo -cf "/etc/sudoers.d/90-${ADMIN_USER}" >/dev/null

  # Drop-in config: key-only login, no root login.
  cat > /etc/ssh/sshd_config.d/99-sakir-ai.conf <<EOF
# Sakir AI 001 — SSH hardening (written by install.sh)
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
MaxAuthTries 4
LoginGraceTime 30
X11Forwarding no
AllowUsers ${ADMIN_USER}
EOF
  sshd -t || die "sshd config test failed; nothing was reloaded."
  systemctl reload ssh 2>/dev/null || systemctl reload sshd
  ok "SSH hardened: key-only login as ${ADMIN_USER}, root login disabled"
  warn "Open a NEW terminal and test 'ssh ${ADMIN_USER}@<server-ip>' before closing this one."
  mark_done admin
}

# =============================================================================
# Step: firewall
# =============================================================================
step_firewall() {
  section "Firewall (UFW) and fail2ban"
  ufw default deny incoming
  ufw default allow outgoing
  ufw allow OpenSSH
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw --force enable
  ok "UFW enabled: 22, 80, 443 open"

  # Docker publishes ports around UFW, so compose.yml binds every admin port
  # to 127.0.0.1 only. Nothing else is reachable from the internet.

  cat > /etc/fail2ban/jail.d/sakir-ai.local <<'EOF'
# Sakir AI 001 — ban IPs that keep failing SSH or hammer the webhook
[sshd]
enabled  = true
backend  = systemd
maxretry = 5
findtime = 10m
bantime  = 1h

[nginx-limit-req]
enabled  = true
port     = http,https
logpath  = /var/log/nginx/error.log
maxretry = 20
findtime = 10m
bantime  = 1h
EOF
  systemctl enable --now fail2ban
  systemctl restart fail2ban
  ok "fail2ban active for SSH and Nginx rate limits"
}

# =============================================================================
# Step: docker  (official Docker apt repository, not the convenience script)
# =============================================================================
step_docker() {
  section "Docker Engine and Compose"
  if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
    info "Docker already installed: $(docker --version)"
  else
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    # shellcheck disable=SC1091
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
      > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  fi

  # Log rotation for every container + keep containers running during daemon restarts.
  mkdir -p /etc/docker
  cat > /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "20m", "max-file": "5" },
  "live-restore": true
}
EOF
  systemctl enable --now docker
  systemctl restart docker
  usermod -aG docker "$ADMIN_USER" 2>/dev/null || true
  ok "$(docker --version); $(docker compose version)"
}

# =============================================================================
# Step: layout  (copy the bundle to /opt/sakir-ai and create folders)
# =============================================================================
step_layout() {
  section "Folder layout in ${INSTALL_DIR}"
  mkdir -p "$INSTALL_DIR"

  # Copy code and configs. Never overwrite data, secrets, knowledge or backups.
  rsync -a --delete \
    --exclude '.state/' --exclude 'data/' --exclude 'secrets/' \
    --exclude 'knowledge/' --exclude 'backups/' --exclude 'outbox/' \
    --exclude 'hostops/queue/' --exclude 'hostops/done/' \
    --exclude '.env' \
    "${BUNDLE_DIR}/" "${INSTALL_DIR}/"

  # Persistent folders.
  local d
  for d in data/hermes data/n8n data/n8n-db data/ai-db data/qdrant data/models \
           data/kuma data/loki data/grafana data/safe-exec-audit \
           outbox/public secrets backups hostops/queue hostops/done; do
    mkdir -p "${INSTALL_DIR}/${d}"
  done

  chmod 700 "${INSTALL_DIR}/secrets" "${INSTALL_DIR}/backups"
  chmod 700 "${INSTALL_DIR}/hostops/queue"
  chmod 755 "${INSTALL_DIR}/hostops/done"
  # Container users (uid 10001 in our images; n8n uses 1000; Grafana 472; Loki 10001).
  chown -R 1000:1000   "${INSTALL_DIR}/data/n8n"
  chown -R 472:0       "${INSTALL_DIR}/data/grafana"
  chown -R 10001:10001 "${INSTALL_DIR}/data/loki" "${INSTALL_DIR}/data/models" "${INSTALL_DIR}/outbox"
  chmod +x "${INSTALL_DIR}"/scripts/*.sh "${INSTALL_DIR}/hostops/sakir-hostops" "${INSTALL_DIR}/install.sh"

  # Command shortcut: `sakir-ai status`, `sakir-ai logs hermes`, ...
  ln -sf "${INSTALL_DIR}/scripts/sakir-ai.sh" /usr/local/bin/sakir-ai
  ok "Layout ready; use the 'sakir-ai' command for daily operations"
}

# =============================================================================
# Step: secrets  (ask for external tokens, generate internal passwords)
# =============================================================================
step_secrets() {
  section "Secrets and settings"
  local S="${INSTALL_DIR}/secrets"
  local ENVF="${INSTALL_DIR}/.env"
  touch "$ENVF"; chmod 600 "$ENVF"

  info "Values already saved are kept; press Enter to keep them."
  echo

  # ---- Public settings (.env read by docker compose) ----
  local domain email
  local cur_domain; cur_domain="$(env_get "$ENVF" PUBLIC_DOMAIN)"
  ask domain "Public domain for webhooks (must point to this server)" "${cur_domain:-ai.datatechbd.com}"
  ask email "Email for Let's Encrypt notices" "$(env_get "$ENVF" LETSENCRYPT_EMAIL)"
  env_set "$ENVF" COMPOSE_PROJECT_NAME "sakir-ai"
  env_set "$ENVF" PUBLIC_DOMAIN "$domain"
  env_set "$ENVF" LETSENCRYPT_EMAIL "$email"
  env_set "$ENVF" TZ "$TIMEZONE"
  # Image versions: copy any tag not yet in .env (your pinned tags are kept).
  local line key
  while IFS= read -r line; do
    [[ "$line" =~ ^[A-Z_]+= ]] || continue
    key="${line%%=*}"
    env_ensure "$ENVF" "$key" "${line#*=}"
  done < "${INSTALL_DIR}/versions.env"

  # ---- External secrets (you create these; see README "Before you install") ----
  local owner hermes_bot sales_bot or_sales meta_secret meta_page meta_token ig_user
  ask owner "Your numeric Telegram user ID (from @userinfobot)" "$(env_get "$S/dt-assistant.env" TELEGRAM_OWNER_ID)"
  ask_secret hermes_bot "Token of @SakirAI_bot (Hermes, from @BotFather)"
  ask_secret sales_bot  "Token of @DTSalesDesk_bot (approvals, from @BotFather)"
  ask_secret or_sales   "OpenRouter API key for SALES (limit about \$26/month)"
  ask_secret meta_secret "Meta App Secret (developers.facebook.com > App settings > Basic)"
  ask meta_page "Facebook Page ID" "$(env_get "$S/dt-assistant.env" META_PAGE_ID)"
  ask_secret meta_token "Facebook long-lived Page access token"
  ask ig_user "Instagram business account ID (optional)" "$(env_get "$S/dt-assistant.env" IG_USER_ID)"

  # ---- Internal secrets (generated once, never shown) ----
  local ai_db_pw ro_pw n8n_db_pw n8n_key safe_token internal_token verify_token grafana_pw
  ai_db_pw="$(env_get "$S/ai-db.env" POSTGRES_PASSWORD)";        [[ -n "$ai_db_pw" ]]   || ai_db_pw="$(gen_secret)"
  ro_pw="$(env_get "$S/ai-db.env" HERMES_RO_PASSWORD)";          [[ -n "$ro_pw" ]]      || ro_pw="$(gen_secret)"
  n8n_db_pw="$(env_get "$S/n8n-db.env" POSTGRES_PASSWORD)";      [[ -n "$n8n_db_pw" ]]  || n8n_db_pw="$(gen_secret)"
  n8n_key="$(env_get "$S/n8n.env" N8N_ENCRYPTION_KEY)";          [[ -n "$n8n_key" ]]    || n8n_key="$(gen_secret)"
  safe_token="$(env_get "$S/safe-exec.env" SAFE_EXEC_TOKEN)";    [[ -n "$safe_token" ]] || safe_token="$(gen_secret)"
  internal_token="$(env_get "$S/dt-assistant.env" INTERNAL_API_TOKEN)"; [[ -n "$internal_token" ]] || internal_token="$(gen_secret)"
  verify_token="$(env_get "$S/dt-assistant.env" META_VERIFY_TOKEN)";    [[ -n "$verify_token" ]]   || verify_token="$(gen_secret)"
  grafana_pw="$(env_get "$S/grafana.env" GF_SECURITY_ADMIN_PASSWORD)";  [[ -n "$grafana_pw" ]]     || grafana_pw="$(gen_secret)"

  # helper: set only when a new value was typed (empty answer keeps the old one)
  _set_if() { [[ -n "$3" ]] && env_set "$1" "$2" "$3" || env_ensure "$1" "$2" ""; }

  # ai-db (Postgres for leads, messages, approvals, spend, audit)
  env_set "$S/ai-db.env" POSTGRES_DB sakirai
  env_set "$S/ai-db.env" POSTGRES_USER sakirai
  env_set "$S/ai-db.env" POSTGRES_PASSWORD "$ai_db_pw"
  env_set "$S/ai-db.env" HERMES_RO_PASSWORD "$ro_pw"

  # n8n and its database
  env_set "$S/n8n-db.env" POSTGRES_DB n8n
  env_set "$S/n8n-db.env" POSTGRES_USER n8n
  env_set "$S/n8n-db.env" POSTGRES_PASSWORD "$n8n_db_pw"
  env_set "$S/n8n.env" DB_POSTGRESDB_DATABASE n8n
  env_set "$S/n8n.env" DB_POSTGRESDB_USER n8n
  env_set "$S/n8n.env" DB_POSTGRESDB_PASSWORD "$n8n_db_pw"
  env_set "$S/n8n.env" N8N_ENCRYPTION_KEY "$n8n_key"

  # safe-exec (sends approval codes with the Hermes bot token)
  env_set "$S/safe-exec.env" SAFE_EXEC_TOKEN "$safe_token"
  env_set "$S/safe-exec.env" TELEGRAM_OWNER_ID "$owner"
  _set_if "$S/safe-exec.env" TELEGRAM_BOT_TOKEN "$hermes_bot"

  # dt-assistant (sales pipeline, approvals bot, publisher, internal API)
  local D="$S/dt-assistant.env"
  env_set "$D" DATABASE_URL "postgresql://sakirai:${ai_db_pw}@ai-db:5432/sakirai"
  env_set "$D" TELEGRAM_OWNER_ID "$owner"
  env_set "$D" INTERNAL_API_TOKEN "$internal_token"
  env_set "$D" META_VERIFY_TOKEN "$verify_token"
  env_set "$D" META_PAGE_ID "$meta_page"
  env_set "$D" IG_USER_ID "$ig_user"
  env_set "$D" PUBLIC_BASE_URL "https://${domain}"
  _set_if "$D" SALES_BOT_TOKEN "$sales_bot"
  _set_if "$D" OPENROUTER_API_KEY "$or_sales"
  _set_if "$D" META_APP_SECRET "$meta_secret"
  _set_if "$D" META_PAGE_TOKEN "$meta_token"

  # Hermes extra environment (tools the skills call); Hermes' own LLM key and
  # bot token live in data/hermes/.env, written by its setup wizard.
  local H="$S/hermes.env"
  env_set "$H" SAFE_EXEC_URL "http://safe-exec:8080"
  env_set "$H" SAFE_EXEC_TOKEN "$safe_token"
  env_set "$H" DT_ASSISTANT_URL "http://dt-assistant:8080"
  env_set "$H" INTERNAL_API_TOKEN "$internal_token"
  env_set "$H" STT_URL "http://stt:8000"
  env_set "$H" TTS_URL "http://tts:8000"
  env_set "$H" AI_DB_RO_URL "postgresql://hermes_ro:${ro_pw}@ai-db:5432/sakirai"

  # Grafana admin
  env_set "$S/grafana.env" GF_SECURITY_ADMIN_USER admin
  env_set "$S/grafana.env" GF_SECURITY_ADMIN_PASSWORD "$grafana_pw"
  env_set "$S/grafana.env" GF_USERS_ALLOW_SIGN_UP false
  env_set "$S/grafana.env" GF_ANALYTICS_REPORTING_ENABLED false

  # Pre-seed Hermes' own .env so its wizard finds the Telegram settings.
  local HE="${INSTALL_DIR}/data/hermes/.env"
  touch "$HE"; chmod 600 "$HE"
  [[ -n "$hermes_bot" ]] && env_set "$HE" TELEGRAM_BOT_TOKEN "$hermes_bot"
  [[ -n "$owner" ]] && env_set "$HE" TELEGRAM_ALLOWED_USERS "$owner"

  chown -R root:root "$S"; chmod 600 "$S"/*.env

  # Report what is still missing (without printing values).
  local missing=()
  [[ -n "$(env_get "$D" TELEGRAM_OWNER_ID)" ]] || missing+=("Telegram user ID")
  [[ -n "$(env_get "$S/safe-exec.env" TELEGRAM_BOT_TOKEN)" ]] || missing+=("@SakirAI_bot token")
  [[ -n "$(env_get "$D" SALES_BOT_TOKEN)" ]] || missing+=("@DTSalesDesk_bot token")
  [[ -n "$(env_get "$D" OPENROUTER_API_KEY)" ]] || missing+=("OpenRouter sales key")
  [[ -n "$(env_get "$D" META_PAGE_TOKEN)" ]] || missing+=("Meta Page token (sales stays off)")
  if ((${#missing[@]})); then
    warn "Not set yet: ${missing[*]}"
    warn "Add later with: sudo bash ${INSTALL_DIR}/install.sh --step secrets && sakir-ai restart"
  fi

  info "Meta webhook settings for developers.facebook.com:"
  info "  Callback URL: https://${domain}/meta/webhook"
  info "  Verify token: stored in ${D} (META_VERIFY_TOKEN); show it with: sakir-ai secret META_VERIFY_TOKEN"
  ok "Secrets saved in ${S} (mode 600, root only)"
}

# =============================================================================
# Step: knowledge  (Git repo of Markdown files that agents read)
# =============================================================================
step_knowledge() {
  section "Knowledge base"
  local K="${INSTALL_DIR}/knowledge"
  if [[ ! -d "$K/.git" ]]; then
    mkdir -p "$K"
    rsync -a --ignore-existing "${BUNDLE_DIR}/knowledge-templates/" "$K/"
    git -C "$K" init -q -b main
    git -C "$K" config user.name "Sakir AI"
    git -C "$K" config user.email "sakir-ai@localhost"
    git -C "$K" add -A
    git -C "$K" commit -q -m "Initial knowledge templates"
    ok "Knowledge repo created at $K"
  else
    info "Knowledge repo exists; templates not copied over your files"
  fi
  mkdir -p "$K/inbox"
  # Readable by every container user; inbox writable by Hermes (uid 10001).
  chmod -R a+rX "$K"
  chown -R 10001:10001 "$K/inbox"
  warn "Fill in TODOs, especially products/dt-restora/pricing.md, before the sales agent goes live."
}

# =============================================================================
# Step: nginx  (public reverse proxy; only three public paths)
# =============================================================================
step_nginx() {
  section "Nginx reverse proxy"
  local domain; domain="$(env_get "${INSTALL_DIR}/.env" PUBLIC_DOMAIN)"
  [[ -n "$domain" ]] || die "PUBLIC_DOMAIN not set; run --step secrets first."

  install -m 644 "${INSTALL_DIR}/config/nginx/sakir-ai-ratelimit.conf" /etc/nginx/conf.d/sakir-ai-ratelimit.conf
  sed "s/__DOMAIN__/${domain}/g; s#__INSTALL_DIR__#${INSTALL_DIR}#g" \
    "${INSTALL_DIR}/config/nginx/sakir-ai.conf.template" > /etc/nginx/sites-available/sakir-ai.conf
  # Servers with IPv6 disabled in the kernel cannot open [::] sockets.
  if [[ ! -e /proc/net/if_inet6 ]]; then
    sed -i '/listen \[::\]:80;/d' /etc/nginx/sites-available/sakir-ai.conf
    info "IPv6 is disabled on this server; listening on IPv4 only"
  fi
  ln -sf /etc/nginx/sites-available/sakir-ai.conf /etc/nginx/sites-enabled/sakir-ai.conf
  rm -f /etc/nginx/sites-enabled/default

  # Hide the Nginx version in error pages and headers.
  sed -i 's/# *server_tokens off;/server_tokens off;/' /etc/nginx/nginx.conf

  nginx -t
  systemctl enable --now nginx
  systemctl reload nginx
  ok "Nginx serves ${domain}: /meta/webhook, /hooks/*, /public-media/*"
}

# =============================================================================
# Step: tls  (Let's Encrypt; skipped until DNS points to this server)
# =============================================================================
step_tls() {
  section "TLS certificate"
  local domain email ip dns
  domain="$(env_get "${INSTALL_DIR}/.env" PUBLIC_DOMAIN)"
  email="$(env_get "${INSTALL_DIR}/.env" LETSENCRYPT_EMAIL)"
  ip="$(public_ip)"
  dns="$(dig +short A "$domain" | tail -n1)"

  if [[ "$dns" != "$ip" ]]; then
    warn "DNS for ${domain} points to '${dns:-nothing}', this server is ${ip}."
    warn "Create an A record ${domain} -> ${ip}, wait a few minutes, then run:"
    warn "  sudo bash ${INSTALL_DIR}/install.sh --step tls"
    return 0   # not marked done
  fi
  [[ -n "$email" ]] || die "LETSENCRYPT_EMAIL is empty; run --step secrets."

  certbot --nginx -d "$domain" --non-interactive --agree-tos -m "$email" --redirect
  systemctl reload nginx
  # Renewal runs from the certbot systemd timer installed by the package.
  systemctl list-timers | grep -q certbot && ok "Auto-renewal timer active"
  ok "HTTPS enabled for ${domain}"
  mark_done tls
}

# =============================================================================
# Step: hostops  (root runner for allowlisted host actions)
# =============================================================================
step_hostops() {
  section "Host action runner (safe-exec bridge)"
  install -m 750 -o root -g root "${INSTALL_DIR}/hostops/sakir-hostops" /usr/local/bin/sakir-hostops
  install -m 644 "${INSTALL_DIR}/systemd/sakir-hostops.path"    /etc/systemd/system/
  install -m 644 "${INSTALL_DIR}/systemd/sakir-hostops.service" /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable --now sakir-hostops.path
  ok "sakir-hostops.path watching ${INSTALL_DIR}/hostops/queue"
}

# =============================================================================
# Step: stack  (build our images and start every container except Hermes)
# =============================================================================
step_stack() {
  section "Build and start the containers"
  cd "$INSTALL_DIR"
  docker compose pull --ignore-buildable --quiet
  docker compose build --pull
  # Hermes starts in the next step, after its setup wizard.
  docker compose up -d --remove-orphans \
    ai-db n8n-db qdrant stt tts safe-exec dt-assistant n8n uptime-kuma loki alloy grafana
  info "First start downloads speech models (about 2 GB); stt may take 5-10 minutes to become healthy."
  ok "Containers started: $(docker compose ps --services --status running | tr '\n' ' ')"
}

# =============================================================================
# Step: hermes  (setup wizard, skills, start)
# =============================================================================
step_hermes() {
  section "Hermes Agent"
  cd "$INSTALL_DIR"
  local H="${INSTALL_DIR}/data/hermes"

  # Install our skills (overwrites our own skill folders only).
  mkdir -p "$H/skills"
  rsync -a "${INSTALL_DIR}/hermes/skills/" "$H/skills/"
  ok "Installed $(find "${INSTALL_DIR}/hermes/skills" -name SKILL.md | wc -l) Sakir skills"

  if [[ ! -f "$H/config.yaml" ]]; then
    if [[ "$NON_INTERACTIVE" == "1" ]]; then
      warn "Hermes is not configured. Run: sudo bash ${INSTALL_DIR}/install.sh --step hermes"
      return 0
    fi
    info "Starting the Hermes setup wizard. Choose:"
    info "  Provider: OpenRouter  -> paste your 'hermes-core' OpenRouter key"
    info "  Model:    deepseek/deepseek-v3.2   (fallback: google/gemini-2.5-flash)"
    info "  Messaging: Telegram   -> bot token and allowed user are pre-filled; confirm them"
    docker compose run --rm hermes setup </dev/tty
  else
    info "Hermes already configured (config.yaml exists)"
  fi

  docker compose up -d hermes
  ok "Hermes started. Message @SakirAI_bot on Telegram to test."
  mark_done hermes
}

# =============================================================================
# Step: timers  (backups 03:00, knowledge index 02:30, Asia/Dhaka)
# =============================================================================
step_timers() {
  section "Scheduled jobs (systemd timers)"
  local unit
  for unit in sakir-backup.service sakir-backup.timer sakir-index.service sakir-index.timer; do
    install -m 644 "${INSTALL_DIR}/systemd/${unit}" /etc/systemd/system/
  done
  systemctl daemon-reload
  systemctl enable --now sakir-backup.timer sakir-index.timer

  # Backup encryption key: public key on the server, private key with Sakir.
  if [[ ! -s /root/backup-recipient.txt ]]; then
    local pub=""
    ask pub "age public key for backups (starts with age1...; Enter to generate one now)" ""
    if [[ -z "$pub" ]]; then
      local tmpkey; tmpkey="$(mktemp)"
      age-keygen -o "$tmpkey" 2>/dev/null
      age-keygen -y "$tmpkey" > /root/backup-recipient.txt
      echo
      warn "================ BACKUP PRIVATE KEY — SAVE IT NOW ================"
      cat "$tmpkey"
      warn "Store this in your password manager. Without it backups cannot be"
      warn "restored. It will now be deleted from the server."
      warn "=================================================================="
      [[ "$NON_INTERACTIVE" == "1" ]] || read -r -p "  Type 'saved' when the key is stored: " _ </dev/tty
      shred -u "$tmpkey"
    else
      echo "$pub" > /root/backup-recipient.txt
    fi
    chmod 600 /root/backup-recipient.txt
  fi

  if ! rclone listremotes 2>/dev/null | grep -q '^sakir-backup:'; then
    warn "Off-server copy not configured. Backups stay local until you run:"
    warn "  sudo rclone config   (create a remote named 'sakir-backup', e.g. Backblaze B2)"
  fi
  ok "Timers: $(systemctl list-timers --no-legend 'sakir-*' | awk '{print $NF}' | tr '\n' ' ')"
}

# =============================================================================
# Step: tailscale  (optional private access to admin screens)
# =============================================================================
step_tailscale() {
  section "Tailscale (private admin access)"
  if ! command -v tailscale >/dev/null; then
    if ! confirm "Install Tailscale for private access to n8n, Grafana and Uptime Kuma?"; then
      info "Skipped. You can use SSH tunnels instead (see README)."
      return 0
    fi
    curl -fsSL https://tailscale.com/install.sh | sh
  fi
  if ! tailscale status >/dev/null 2>&1; then
    info "Log in to Tailscale with the link that appears:"
    tailscale up --ssh=false
  fi
  # Expose admin UIs to your tailnet only (HTTPS, tailnet certificate).
  tailscale serve --bg --https=8443 http://127.0.0.1:5678 >/dev/null   # n8n
  tailscale serve --bg --https=3443 http://127.0.0.1:3000 >/dev/null   # Grafana
  tailscale serve --bg --https=3444 http://127.0.0.1:3001 >/dev/null   # Uptime Kuma
  local ts_name; ts_name="$(tailscale status --json | jq -r '.Self.DNSName' | sed 's/\.$//')"
  ok "Private URLs (only on your tailnet):"
  ok "  n8n:         https://${ts_name}:8443"
  ok "  Grafana:     https://${ts_name}:3443"
  ok "  Uptime Kuma: https://${ts_name}:3444"
  mark_done tailscale
}

# =============================================================================
# Step: aitools  (optional AI coding tools for Sakir, see docs/AI-TOOLS.md)
# =============================================================================
step_aitools() {
  section "AI coding tools (optional)"
  if [[ "$NON_INTERACTIVE" == "1" ]]; then
    info "Skipped in non-interactive mode. Later: sudo bash ${INSTALL_DIR}/scripts/install-ai-tools.sh"
    return 0
  fi
  ADMIN_USER="$ADMIN_USER" bash "${INSTALL_DIR}/scripts/install-ai-tools.sh"
}

# =============================================================================
# Step: verify
# =============================================================================
step_verify() {
  section "Verification"
  "${INSTALL_DIR}/scripts/healthcheck.sh" || warn "Some checks failed; see above."
}

# =============================================================================
# Runner
# =============================================================================
usage() { awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"; }   # prints the header comment

list_steps() {
  local s
  for s in "${STEPS[@]}"; do
    if step_done "$s"; then printf '  %-10s done\n' "$s"; else printf '  %-10s -\n' "$s"; fi
  done
}

run_step() {
  local s="$1"
  "step_${s}"
  # Steps that mark themselves (admin, tls, hermes, tailscale) only do so when
  # fully complete; the rest are marked here.
  case "$s" in admin|tls|hermes|tailscale) ;; *) mark_done "$s" ;; esac
}

main() {
  local only="" from="" force=0
  while (($#)); do
    case "$1" in
      --step) only="$2"; shift 2 ;;
      --from) from="$2"; shift 2 ;;
      --force) force=1; shift ;;
      --non-interactive) NON_INTERACTIVE=1; shift ;;
      --list) list_steps; exit 0 ;;
      -h|--help) usage; exit 0 ;;
      *) die "Unknown option: $1 (see --help)" ;;
    esac
  done

  require_root
  mkdir -p "$(dirname "$LOG_FILE")"; touch "$LOG_FILE"; chmod 600 "$LOG_FILE"
  info "Sakir AI 001 installer — bundle at ${BUNDLE_DIR}, target ${INSTALL_DIR}"

  if [[ -n "$only" ]]; then
    declare -F "step_${only}" >/dev/null || die "Unknown step: $only"
    run_step "$only"; exit 0
  fi

  local started=0 s
  [[ -z "$from" ]] && started=1
  for s in "${STEPS[@]}"; do
    [[ "$s" == "$from" ]] && started=1
    ((started)) || continue
    if step_done "$s" && ((force == 0)) && [[ -z "$from" ]]; then
      info "Skipping '$s' (already done; use --step $s to re-run)"
      continue
    fi
    run_step "$s"
  done

  section "Done"
  ok "Sakir AI 001 is installed. Next steps are in ${INSTALL_DIR}/README.md (section 'After install')."
}

main "$@"
