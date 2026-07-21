FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# No opentelemetry-instrument wrapper here: Traceloop.init() owns the tracer provider and
# instruments the LLM client; FastAPI is instrumented in-app. OTLP endpoint comes from .env.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
