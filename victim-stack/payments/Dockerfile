FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
# Bootstrap installs matching instrumentors (FastAPI, httpx, logging, …) for auto-wiring.
RUN pip install --no-cache-dir -r requirements.txt \
    && opentelemetry-bootstrap -a install

COPY app.py .

# Shorter metric export interval so orphan/cardinality series show up fast in the demo.
ENV OTEL_TRACES_EXPORTER=otlp \
    OTEL_METRICS_EXPORTER=otlp \
    OTEL_LOGS_EXPORTER=otlp \
    OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true \
    OTEL_METRIC_EXPORT_INTERVAL=15000

CMD ["opentelemetry-instrument", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
