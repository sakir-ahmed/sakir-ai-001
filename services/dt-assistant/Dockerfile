# dt-assistant: sales pipeline, approval desk bot, publisher, internal API.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && useradd --uid 10001 --no-create-home app
COPY app ./app

USER app
EXPOSE 8080
# One worker: the event queue and Telegram polling must exist exactly once.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "*"]
