# Server inventory

## sakir-ai VPS
- Provider: TODO   Plan: Cloud VPS 12 (12 vCPU, 48 GB RAM, 200 GB NVMe / 400 GB SSD)
- OS: Ubuntu TODO   Public IP: TODO   Domain: TODO (webhooks)
- Runs: Sakir AI stack (/opt/sakir-ai). DT products: none yet.

## What "healthy" means
- All containers running; dt-assistant, stt, safe-exec, ai-db healthy.
- Disk under 80%, memory under 85%.
- SSL certificates valid for more than 14 days.
- Backup file from the last 24 hours in /opt/sakir-ai/backups.
- Nginx 5xx errors under 1% of requests.

## DT product servers
- TODO: list each server, domain, containers and database.
