# tts: Bangla/English text-to-speech via edge-tts.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp

RUN pip install --no-cache-dir edge-tts==7.3.1 fastapi==0.115.12 uvicorn==0.34.2 \
 && useradd --uid 10001 --no-create-home app
USER app
WORKDIR /app
COPY app.py .

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
