#!/usr/bin/env bash
# Configure a dedicated public AI hostname without replacing unrelated Nginx sites.
# Reuses committed routes, existing ACME account and private environment settings.
# Usage: sudo bash scripts/setup-public-domain.sh ai001.sakir.bd
set -Eeuo pipefail
INSTALL_DIR="${INSTALL_DIR:-/opt/sakir-ai}"
# shellcheck source=../lib/common.sh
source "${INSTALL_DIR}/lib/common.sh"
require_root
domain="${1:?Usage: setup-public-domain.sh <public-hostname>}"
[[ "$domain" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$ && "$domain" == *.* && "$domain" != *..* ]] \
  || die "Use a plain lowercase DNS hostname, without a scheme, port or path"
[[ ${#domain} -le 253 ]] || die "Hostname is too long"
for command in nginx certbot curl; do command -v "$command" >/dev/null || die "Missing command: $command"; done
[[ -s "${INSTALL_DIR}/config/nginx/sakir-ai.conf.template" ]] || die "Nginx template missing"
[[ -s /etc/nginx/conf.d/sakir-ai-ratelimit.conf ]] || die "Install existing Sakir rate-limit config first"
# This command never registers a new ACME account or accepts new terms silently.
find /etc/letsencrypt/accounts -name regr.json -print -quit 2>/dev/null | grep -q . \
  || die "No existing ACME account; owner must configure certbot account first"
nginx -t
"${INSTALL_DIR}/scripts/backup.sh"

site="/etc/nginx/sites-available/${domain}.conf"
enabled="/etc/nginx/sites-enabled/${domain}.conf"
rollback="/var/backups/sakir-ai-domain/$(date +%Y%m%d-%H%M%S)"
install -d -m 700 "$rollback"
if [[ -e "$site" ]]; then cp -p "$site" "$rollback/site.conf"; fi
candidate="$(mktemp "$rollback/candidate.XXXX")"
sed "s/__DOMAIN__/${domain}/g; s#__INSTALL_DIR__#${INSTALL_DIR}#g" \
  "${INSTALL_DIR}/config/nginx/sakir-ai.conf.template" > "$candidate"
if [[ ! -e /proc/net/if_inet6 ]]; then
  sed -i '/listen \[::\]:80;/d' "$candidate"
fi
# Existing HTTPS config can be reused for renewals instead of being overwritten.
if [[ ! -s "$site" ]]; then
  install -m 644 "$candidate" "$site"
fi
if [[ ! -e "$enabled" && ! -L "$enabled" ]]; then ln -s "$site" "$enabled"; fi
nginx -t
systemctl reload nginx
# Keeps Cloudflare proxy enabled; no direct-DNS equality precondition is used.
# HTTP-01 must reach this hostname through Cloudflare for issuance to succeed.
certbot --nginx -d "$domain" --non-interactive --redirect
nginx -t
systemctl reload nginx
path='/meta/webhook?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=1'
origin_code="$(curl -sS --max-time 15 --resolve "${domain}:443:127.0.0.1" \
  -o /dev/null -w '%{http_code}' "https://${domain}${path}")"
[[ "$origin_code" == 403 ]] || die "Origin route failed acceptance: HTTP ${origin_code}; settings unchanged"
public_code="$(curl -sS --max-time 20 -o /dev/null -w '%{http_code}' "https://${domain}${path}")"
[[ "$public_code" == 403 ]] || die "Public route failed acceptance: HTTP ${public_code}; settings unchanged"
env_set "${INSTALL_DIR}/.env" PUBLIC_DOMAIN "$domain"
ok "Origin TLS and public webhook verified; PUBLIC_DOMAIN=${domain}"
info "Existing container environment is unchanged; n8n hostname refresh requires a separate reviewed deployment."
info "Existing old-domain site was preserved. Prior dedicated-site config (if any): ${rollback}"
