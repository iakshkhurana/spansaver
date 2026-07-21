# SpanSaver auditor — FastAPI brain. Runs inside the SigNoz docker network so it reaches
# ClickHouse (native 9000) and the SigNoz API by name. Build context is ./auditor.
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Package lands at /app/auditor so `import auditor.*` works with PYTHONPATH=/app.
COPY . /app/auditor
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

EXPOSE 8100
CMD ["uvicorn", "auditor.main:app", "--host", "0.0.0.0", "--port", "8100"]
