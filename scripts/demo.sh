#!/usr/bin/env bash
# SpanSaver seeded end-to-end rehearsal (D4 DoD): detect -> prove -> fix -> verify, start to
# finish, WITHOUT touching a terminal mid-flow. Drives the live auditor API exactly like the UI
# buttons do, and narrates each step so it reads on camera.
#
# Assumes the stack is up with data flowing:  make up && make waste-on && make traffic
# Env: AUDITOR_PORT (default 8100), DEMO_WAIT seconds to let post-apply data land (default 60).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Read AUDITOR_PORT from .env without sourcing it (the file may have CRLF/Windows line endings,
# which `source` chokes on). Strip CR + whitespace. An exported env var, if set, wins.
PORT="${AUDITOR_PORT:-}"
if [ -z "$PORT" ] && [ -f "$ROOT/.env" ]; then
  PORT="$(grep -E '^AUDITOR_PORT=' "$ROOT/.env" | tail -1 | cut -d= -f2- | tr -d '\r\n[:space:]')"
fi
PORT="${PORT:-8100}"
BASE="http://localhost:${PORT}"
export DEMO_WAIT="${DEMO_WAIT:-60}"

if [ -t 1 ]; then B=$'\e[1m'; D=$'\e[2m'; G=$'\e[32m'; C=$'\e[36m'; R=$'\e[31m'; X=$'\e[0m'; else B=; D=; G=; C=; R=; X=; fi
step() { printf '\n%s\n' "${B}${C}== $* ==${X}"; }
info() { printf '%s\n' "${D}$*${X}"; }
die()  { printf '%s\n' "${R}x $*${X}" >&2; exit 1; }
# api METHOD PATH -> echoes the response body; caller captures it (never pipe a heredoc onto it,
# a heredoc would steal python's stdin from the pipe).
api()  { curl -sf -X "$1" "${BASE}$2"; }

printf '\n%s\n' "${B}${C}### SpanSaver — detect · prove · fix · verify${X}"
info "auditor ${BASE} · post-apply wait ${DEMO_WAIT}s"

# ── 1 · health ──
step "1/5 · backend health"
RESP="$(api GET /health)" || die "auditor unreachable at ${BASE} — up? (docker compose up -d --build auditor)"
RESP="$RESP" python3 <<'PY' || die "ClickHouse not reachable — bring SigNoz up first."
import os, sys, json
d = json.loads(os.environ["RESP"])
ch, sz = d["clickhouse"], d["signoz_api"]
print(f"  status      {d['status']}")
print(f"  clickhouse  {'ok' if ch['ok'] else 'FAIL ' + ch['error']}")
print(f"  signoz_api  {'ok' if sz['ok'] else 'FAIL ' + sz['error']}")
sys.exit(0 if ch["ok"] else 1)
PY

# ── 2 · audit ──
step "2/5 · audit — detect every leak (live queries)"
RESP="$(api POST /audit)" || die "audit request failed"
RESP="$RESP" python3 <<'PY' || die "audit failed / no findings — run: make waste-on && make traffic, then wait."
import os, json
d = json.loads(os.environ["RESP"]); total = 0.0
if not d.get("count"):
    raise SystemExit("no findings")
print(f"  {d['count']} findings\n")
print(f"  {'ID':<4}{'$ / MONTH':>12}  {'SAFE':<7}LEAK")
for f in sorted(d["findings"], key=lambda f: -f["money"].get("cost_month", 0)):
    m = f["money"].get("cost_month", 0.0); total += m
    safe = "safe" if f["safety"].get("safe") else "REVIEW"
    print(f"  {f['id']:<4}{('$%.2f' % m):>12}  {safe:<7}{f['title']}")
print(f"\n  == total leaking  ${total:,.2f}/mo")
PY

# ── fix + verify one finding, end to end ──
demo_fix() {
  local id="$1" title="$2" resp
  step "$title"
  resp="$(api GET "/findings/${id}")" || die "no finding ${id} — was the audit run?"
  RESP="$resp" python3 <<'PY'
import os, json
d = json.loads(os.environ["RESP"])
print(f"  leak   {d['summary']}")
print(f"  proof  {d['safety'].get('proof', '')}")
PY
  info "  -> applying fix..."
  resp="$(api POST "/apply/${id}")" || die "apply ${id} failed"
  RESP="$resp" python3 <<'PY'
import os, json
d = json.loads(os.environ["RESP"])
print(f"    {d.get('status')} · {d.get('patch') or d.get('target') or d.get('applied') or ''}")
PY
  info "  -> waiting ${DEMO_WAIT}s for post-apply data to land..."
  sleep "$DEMO_WAIT"
  info "  -> verifying on live metrics..."
  resp="$(api POST "/verify/${id}")" || die "verify ${id} failed"
  RESP="$resp" python3 <<'PY'
import os, json
v = json.loads(os.environ["RESP"])["verification"]; h = v.get("headline", {})
u = h.get("unit", "")
print(f"    before {h.get('before')} {u}  ->  after {h.get('after')} {u}  ({h.get('drop_pct')}% drop)")
print(f"    [{'PASS' if v.get('passed') else 'PENDING'}] {v.get('banner')}")
PY
}

# ── 3 · telemetry money shot ──
demo_fix "T1" "3/5 · fix telemetry waste — T1 debug-log flood"

# ── 4 · LLM money shot ──
demo_fix "L1" "4/5 · fix LLM waste — L1 cacheable duplicate prompts"

# ── 5 · summary ──
step "5/5 · summary"
RESP="$(api GET /findings)" || die "could not fetch findings"
RESP="$RESP" python3 <<'PY'
import os, json
d = json.loads(os.environ["RESP"]); leak = 0.0; rec = 0.0; ver = 0
for f in d["findings"]:
    m = f["money"].get("cost_month", 0.0); leak += m
    if f["status"] == "verified":
        rec += m; ver += 1
print(f"  leaking   ${leak:,.2f}/mo across {d['count']} findings")
print(f"  sealed    ${rec:,.2f}/mo verified ({ver} fix(es) proven on real metrics)")
PY
printf '\n%s\n' "${G}${B}OK demo complete — detect · prove · fix · verify${X}"
info "reset:  make unapply F=T1 && make unapply F=L1   (or: make restore-baseline)"
