#!/usr/bin/env bash
# SpanSaver collector entrypoint: deep-merge baseline + applied patches into merged.yaml,
# then hand off to the OTel Collector. Args (e.g. --config=/etc/otelcol/merged.yaml) come
# from docker-compose `command:`.
set -euo pipefail
cd /etc/otelcol
python3 merge_config.py
exec otelcol-contrib "$@"
