# stt: Bangla/English speech-to-text and embeddings, CPU only.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    HOME=/tmp

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

# CPU-only PyTorch keeps the image several GB smaller than the CUDA build.
RUN pip install --no-cache-dir torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Non-root user; /models is a volume owned by uid 10001 (install.sh sets it).
RUN useradd --uid 10001 --create-home --home-dir /home/app app \
 && mkdir -p /models && chown app:app /models
USER app
WORKDIR /app
COPY app.py .

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
