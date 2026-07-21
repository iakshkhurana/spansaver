# SpanSaver collector image: the OTel Collector Contrib binary grafted onto python:slim so
# the entrypoint can deep-merge baseline + patches into merged.yaml at container start.
# (Official contrib images are distroless — no shell/python — so we can't merge inside them.)
ARG OTELCOL_VERSION=0.116.0
# ^ Verified to exist on Docker Hub. Bump if your SigNoz version needs a newer collector.

FROM otel/opentelemetry-collector-contrib:${OTELCOL_VERSION} AS otelcol

FROM python:3.12-slim
RUN pip install --no-cache-dir pyyaml
COPY --from=otelcol /otelcol-contrib /usr/local/bin/otelcol-contrib
WORKDIR /etc/otelcol
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
# Config + merge_config.py + patches/ are bind-mounted at /etc/otelcol by docker-compose.
ENTRYPOINT ["/entrypoint.sh"]
