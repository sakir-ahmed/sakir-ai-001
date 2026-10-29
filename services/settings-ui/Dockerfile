# settings-ui: the web "edit form" for Sakir AI 001's own settings.
#
# Needs the real `docker compose` CLI (not just the Docker SDK) so that
# "Apply" can run `docker compose up -d --force-recreate <service>` from
# inside this container against the host's Docker daemon (via the mounted
# socket) and have it pick up freshly-edited secrets/*.env files — a plain
# `docker restart` keeps the OLD environment a container started with.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Docker CLI + compose plugin only (no daemon; we use the host's via the
# mounted socket). Same apt repo install.sh uses on the host, Debian variant
# because this base image is Debian, not Ubuntu.
RUN apt-get update -y \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && . /etc/os-release \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian ${VERSION_CODENAME} stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update -y \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
