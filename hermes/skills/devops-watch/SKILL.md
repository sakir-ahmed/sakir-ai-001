---
name: devops-watch
description: Check, explain and fix server problems through safe-exec; handle Sakir's "confirm <id> <code>" approvals. Use for server status, logs, errors, disk, SSL, nginx, restarts, reboot, power off, and any message starting with "confirm".
---
# DevOps watch

Every action goes through `python3 /opt/sakir-tools/sakir.py server ...`.
There is no other way to touch the server. Never use docker, ssh or shell
commands against the host.

## Read (run freely)
| Need | Command |
| --- | --- |
| All containers | `server status` |
| Logs of one container | `server logs <name> --tail 200` |
| Errors per container (1h) | `server errors` |
| Disk and memory | `server disk` |
| SSL certificates | `server ssl` |
| Nginx config test | `server nginx-test` |

## Fix (safe: runs immediately, Sakir is notified)
- Restart one container: `server restart <name> --reason "<why>"`
  Only containers in the allowlist can be restarted; databases cannot.
- Reload Nginx: `server nginx-reload --reason "<why>"`
- Renew SSL: `server ssl-renew --reason "<why>"`

Before restarting, read the logs and say in one line what you saw.
Restart at most once per container per hour; if it fails again, stop and tell Sakir.

## Risky (needs Sakir's code)
`server reboot | poweroff | prune-images --reason "<why>"`, `server remove <name> --reason "<why>"`

1. Explain to Sakir what you want to do and why, BEFORE running it.
2. Run it only if he agrees. safe-exec sends HIM a message with a request id
   and a 4-digit code. You never see the code.
3. Wait. When Sakir sends a message like `confirm a1b2c3 4821`, run:
   `server confirm a1b2c3 4821`
4. Report the result. Reboot/power off also need a backup from the last 24h;
   if blocked, offer to wait for the nightly backup.

Never invent, guess or retry codes. Three wrong codes cancel the request.

## Diagnosis pattern
1. `server status` → find unhealthy or restarting containers.
2. `server errors` → which container is noisy.
3. `server logs <name> --tail 200` → the real error.
4. Tell Sakir: what is wrong, likely cause, your proposed fix (one line each).
