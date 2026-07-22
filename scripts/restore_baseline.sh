#!/usr/bin/env bash
# Panic button: drop every applied collector patch and restart the collector back to the pristine
# baseline. The baseline YAML is never touched (golden rule #4) — we only clear collector/patches/.
# LLM fixes (L1/L2) are env flips on askdocs; reverse those with `make unapply F=L1` if needed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PATCHES="$ROOT/collector/patches"
COLLECTOR_CONTAINER="${COLLECTOR_CONTAINER:-signoz-collector-1}"

shopt -s nullglob
removed=0
for f in "$PATCHES"/*.yaml; do rm -f "$f"; removed=$((removed + 1)); done
echo "removed ${removed} active patch(es) from collector/patches/"

if docker compose restart collector >/dev/null 2>&1; then
  echo "collector restarted via docker compose."
elif docker restart "$COLLECTOR_CONTAINER" >/dev/null 2>&1; then
  echo "collector restarted (${COLLECTOR_CONTAINER})."
else
  echo "WARN: could not restart the collector — restart it by hand (docker ps to find its name)." >&2
fi
echo "baseline restored. (askdocs LLM fixes, if applied, revert via: make unapply F=L1)"
