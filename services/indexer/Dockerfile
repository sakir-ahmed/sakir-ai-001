# indexer: one-shot job that loads knowledge/ into Qdrant.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir requests==2.32.3 \
 && useradd --uid 10001 --no-create-home app
USER app
WORKDIR /app
COPY index.py .
CMD ["python", "index.py"]
