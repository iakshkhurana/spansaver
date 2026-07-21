#!/usr/bin/env bash
# Flip every WASTE_* toggle in .env on/off, then rebuild+restart the victim services.
# Usage: scripts/toggle_waste.sh on | off
# Note: ASKDOCS_CACHE is deliberately NOT touched here — it's the L1 *fix*, not a waste seed.
set -euo pipefail

MODE="${1:-}"
case "$MODE" in
  on)  VAL=1 ;;
  off) VAL=0 ;;
  *)   echo "usage: $0 on|off" >&2; exit 1 ;;
esac

ENV_FILE="$(cd "$(dirname "$0")/.." && pwd)/.env"
[ -f "$ENV_FILE" ] || { echo "no .env found — copy .env.example to .env first" >&2; exit 1; }

TOGGLES="WASTE_DEBUG_FLOOD WASTE_ORPHAN_METRICS WASTE_HEALTH_SPANS WASTE_CARDINALITY WASTE_LLM_NOCACHE WASTE_LLM_BLOAT"
for key in $TOGGLES; do
  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s/^${key}=.*/${key}=${VAL}/" "$ENV_FILE"
  else
    echo "${key}=${VAL}" >> "$ENV_FILE"
  fi
done

echo "waste toggles -> ${VAL}; rebuilding victim services..."
docker compose up -d --build orders payments askdocs
echo "done. (traffic keeps running; give it ~10 min for volumes to matter)"
