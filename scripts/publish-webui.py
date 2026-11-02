#!/usr/bin/env python3
"""Add the UI to an existing TLS site after private owner onboarding passes."""
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request


def main():
    if os.geteuid() != 0 or len(sys.argv) != 2:
        raise SystemExit("Usage: sudo python3 publish-webui.py <existing-TLS-hostname>")
    domain = sys.argv[1]
    if not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*\.[a-z]{2,}", domain):
        raise SystemExit("Use a plain lowercase hostname.")
    with urllib.request.urlopen("http://127.0.0.1:8082/api/config", timeout=15) as response:
        config = json.load(response)
    features = config.get("features", {})
    if config.get("onboarding", False) or features.get("enable_signup") is not False or features.get("auth") is not True:
        raise SystemExit("Owner setup incomplete: create administrator and disable signup before publishing.")
    site = Path(f"/etc/nginx/sites-available/{domain}.conf")
    original = site.read_text()
    if "ssl_certificate " not in original or f"server_name {domain};" not in original:
        raise SystemExit("Expected existing domain/TLS configuration missing; no changes made.")
    # Validate the existing TLS certificate without requiring a particular HTTP status.
    subprocess.run(["curl", "--silent", "--show-error", "--resolve", f"{domain}:443:127.0.0.1",
                    "--output", "/dev/null", f"https://{domain}/"], check=True)
    replacement = '''location / {
        client_max_body_size 25m;
        proxy_pass http://127.0.0.1:8082;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_buffering off;
    }'''
    candidate, count = re.subn(r"location /\s*\{\s*return 404;\s*\}", replacement, original)
    if count != 1:
        raise SystemExit("Expected one fallback 404 block; review manually. No changes made.")
    backup = Path("/var/backups/sakir-ai-webui") / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup.mkdir(parents=True, mode=0o700)
    shutil.copy2(site, backup / "site.conf")
    site.write_text(candidate)
    try:
        subprocess.run(["nginx", "-t"], check=True)
        subprocess.run(["systemctl", "reload", "nginx"], check=True)
    except subprocess.CalledProcessError:
        shutil.copy2(backup / "site.conf", site)
        subprocess.run(["nginx", "-t"], check=True)
        subprocess.run(["systemctl", "reload", "nginx"], check=True)
        raise SystemExit("Proxy validation failed; original site restored.") from None
    print(f"UI proxy enabled at https://{domain}; verify public login and existing webhook routes.")


if __name__ == "__main__":
    main()
