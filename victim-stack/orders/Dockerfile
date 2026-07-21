FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
# opentelemetry-bootstrap installs the instrumentation libs matching what's importable
# (FastAPI, logging, …) so `opentelemetry-instrument` can auto-wire them at startup.
RUN pip install --no-cache-dir -r requirements.txt \
    && opentelemetry-bootstrap -a install

COPY app.py .

# OTLP export for all three signals; endpoint (http://collector:4317) comes from .env.
# The logging bridge is what carries DEBUG floods into signoz_logs for the T1 detector.
ENV OTEL_TRACES_EXPORTER=otlp \
    OTEL_METRICS_EXPORTER=otlp \
    OTEL_LOGS_EXPORTER=otlp \
    OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true

CMD ["opentelemetry-instrument", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
